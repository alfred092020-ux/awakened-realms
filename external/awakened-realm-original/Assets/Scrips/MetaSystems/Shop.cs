using System;
using System.Collections.Generic;

namespace AwakenedRealm.MetaSystems
{
    public enum MetaCurrencyType
    {
        Gold,
        Gems,
        SummonTickets
    }

    /// <summary>
    /// Isolated wallet holding nonnegative currency balances for meta-economy
    /// operations (shop purchases, reward grants). All mutations are checked
    /// for nonnegativity; debits are atomic (balance checked before debit).
    /// </summary>
    [Serializable]
    public sealed class MetaWallet
    {
        public long Gold;
        public long Gems;
        public long SummonTickets;

        public long Balance(MetaCurrencyType currency)
        {
            switch (currency)
            {
                case MetaCurrencyType.Gold: return Gold;
                case MetaCurrencyType.Gems: return Gems;
                case MetaCurrencyType.SummonTickets: return SummonTickets;
                default: throw new ArgumentOutOfRangeException(nameof(currency), currency, "Unknown currency.");
            }
        }

        /// <summary>Adds a nonnegative amount to a currency balance.</summary>
        public void Credit(MetaCurrencyType currency, long amount)
        {
            if (amount < 0)
                throw new ArgumentOutOfRangeException(nameof(amount), "Credit amounts must be nonnegative.");
            checked { SetBalance(currency, Balance(currency) + amount); }
        }

        /// <summary>Atomic debit: fails (returning false) without mutation when balance is insufficient.</summary>
        public bool TryDebit(MetaCurrencyType currency, long amount)
        {
            if (amount < 0)
                throw new ArgumentOutOfRangeException(nameof(amount), "Debit amounts must be nonnegative.");
            long balance = Balance(currency);
            if (balance < amount)
                return false;
            SetBalance(currency, checked(balance - amount));
            return true;
        }

        /// <summary>Grants every component of a reward bundle to the wallet and items sink.</summary>
        public void Grant(MetaRewardBundle bundle, IDictionary<string, long> itemSink)
        {
            if (bundle == null)
                throw new ArgumentNullException(nameof(bundle));

            Credit(MetaCurrencyType.Gold, bundle.Gold);
            Credit(MetaCurrencyType.Gems, bundle.Gems);
            Credit(MetaCurrencyType.SummonTickets, bundle.SummonTickets);
            if (itemSink != null)
            {
                foreach (KeyValuePair<string, long> pair in bundle.Items)
                {
                    long existing;
                    itemSink.TryGetValue(pair.Key, out existing);
                    itemSink[pair.Key] = checked(existing + pair.Value);
                }
            }
        }

        void SetBalance(MetaCurrencyType currency, long value)
        {
            if (value < 0)
                throw new InvalidOperationException("Wallet balances cannot go negative.");
            switch (currency)
            {
                case MetaCurrencyType.Gold: Gold = value; break;
                case MetaCurrencyType.Gems: Gems = value; break;
                case MetaCurrencyType.SummonTickets: SummonTickets = value; break;
                default: throw new ArgumentOutOfRangeException(nameof(currency), currency, "Unknown currency.");
            }
        }
    }

    /// <summary>
    /// Immutable shop item definition. <see cref="DailyLimit"/> and
    /// <see cref="WeeklyLimit"/> are per-window purchase caps; 0 = unlimited.
    /// </summary>
    public sealed class MetaShopItem
    {
        public readonly string ItemId;
        public readonly MetaCurrencyType Currency;
        public readonly long Price;
        public readonly int DailyLimit;
        public readonly int WeeklyLimit;
        public readonly MetaRewardBundle Reward;

        public MetaShopItem(
            string itemId,
            MetaCurrencyType currency,
            long price,
            int dailyLimit,
            int weeklyLimit,
            MetaRewardBundle reward)
        {
            if (string.IsNullOrEmpty(itemId))
                throw new ArgumentException("Shop item ID must be a nonempty stable string.", nameof(itemId));
            if (price < 0)
                throw new ArgumentOutOfRangeException(nameof(price), "Price must be nonnegative.");
            if (dailyLimit < 0 || weeklyLimit < 0)
                throw new ArgumentOutOfRangeException("limits", "Purchase limits must be nonnegative (0 = unlimited).");
            if (reward == null)
                throw new ArgumentNullException(nameof(reward));

            ItemId = itemId;
            Currency = currency;
            Price = price;
            DailyLimit = dailyLimit;
            WeeklyLimit = weeklyLimit;
            Reward = reward;
        }
    }

    /// <summary>
    /// Shop state: validated item catalog, per-item daily/weekly purchase
    /// counts driven by caller-supplied reset keys, and atomic purchases
    /// against a caller-provided <see cref="MetaWallet"/>.
    /// </summary>
    public sealed class MetaShopState
    {
        readonly Dictionary<string, MetaShopItem> items =
            new Dictionary<string, MetaShopItem>(StringComparer.Ordinal);
        readonly Dictionary<string, int> dailyCounts = new Dictionary<string, int>(StringComparer.Ordinal);
        readonly Dictionary<string, int> weeklyCounts = new Dictionary<string, int>(StringComparer.Ordinal);

        string dailyKey = string.Empty;
        string weeklyKey = string.Empty;

        public MetaShopState(IEnumerable<MetaShopItem> catalog)
        {
            if (catalog == null)
                throw new ArgumentNullException(nameof(catalog));
            foreach (MetaShopItem item in catalog)
            {
                if (item == null)
                    throw new ArgumentException("Shop catalog must not contain null entries.", nameof(catalog));
                if (items.ContainsKey(item.ItemId))
                    throw new InvalidOperationException("Duplicate shop item ID: " + item.ItemId);
                items.Add(item.ItemId, item);
            }
        }

        public IReadOnlyDictionary<string, MetaShopItem> Items
        {
            get { return items; }
        }

        /// <summary>Applies the caller-supplied UTC day key; resets daily counters on key change.</summary>
        public bool ResetDaily(string utcDayKey)
        {
            if (string.IsNullOrEmpty(utcDayKey))
                throw new ArgumentException("Day key must be nonempty.", nameof(utcDayKey));
            if (string.Equals(dailyKey, utcDayKey, StringComparison.Ordinal))
                return false;
            dailyKey = utcDayKey;
            dailyCounts.Clear();
            return true;
        }

        /// <summary>Applies the caller-supplied UTC week key; resets weekly counters on key change.</summary>
        public bool ResetWeekly(string utcWeekKey)
        {
            if (string.IsNullOrEmpty(utcWeekKey))
                throw new ArgumentException("Week key must be nonempty.", nameof(utcWeekKey));
            if (string.Equals(weeklyKey, utcWeekKey, StringComparison.Ordinal))
                return false;
            weeklyKey = utcWeekKey;
            weeklyCounts.Clear();
            return true;
        }

        public int DailyPurchases(string itemId)
        {
            int count;
            return dailyCounts.TryGetValue(itemId, out count) ? count : 0;
        }

        public int WeeklyPurchases(string itemId)
        {
            int count;
            return weeklyCounts.TryGetValue(itemId, out count) ? count : 0;
        }

        /// <summary>
        /// Atomically purchases an item: debits <paramref name="wallet"/> and
        /// increments the purchase counters only when currency and limits allow.
        /// On any failure nothing mutates. Returns the granted bundle.
        /// </summary>
        public bool TryPurchase(
            string itemId,
            MetaWallet wallet,
            IDictionary<string, long> itemSink,
            out MetaRewardBundle reward)
        {
            if (wallet == null)
                throw new ArgumentNullException(nameof(wallet));

            MetaShopItem item;
            reward = null;
            if (!items.TryGetValue(itemId, out item))
                return false;

            int daily = DailyPurchases(itemId);
            int weekly = WeeklyPurchases(itemId);
            if ((item.DailyLimit > 0 && daily >= item.DailyLimit) ||
                (item.WeeklyLimit > 0 && weekly >= item.WeeklyLimit))
            {
                return false; // limit reached: no mutation
            }

            if (!wallet.TryDebit(item.Currency, item.Price))
                return false; // insufficient funds: no mutation

            // Debit succeeded: record purchase and grant rewards atomically.
            dailyCounts[itemId] = daily + 1;
            weeklyCounts[itemId] = weekly + 1;
            wallet.Grant(item.Reward, itemSink);
            reward = item.Reward;
            return true;
        }
    }
}
