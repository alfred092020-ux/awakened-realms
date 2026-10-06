using System;
using System.Collections.Generic;

namespace AwakenedRealm.MetaSystems
{
    /// <summary>
    /// A single mail message. Title/body are localization keys, not display
    /// text. Expiry is supplied as UTC ticks in the data; this type never
    /// reads wall-clock time. Claim and delete flags are state flags.
    /// </summary>
    [Serializable]
    public sealed class MetaMailMessage
    {
        public readonly string MailId;
        public readonly string TitleKey;
        public readonly string BodyKey;
        public readonly MetaRewardBundle Reward;
        public readonly long ExpiryUtcTicks;

        public bool Claimed;
        public bool Deleted;

        public MetaMailMessage(
            string mailId,
            string titleKey,
            string bodyKey,
            MetaRewardBundle reward,
            long expiryUtcTicks)
        {
            if (string.IsNullOrEmpty(mailId))
                throw new ArgumentException("Mail ID must be a nonempty stable string.", nameof(mailId));
            if (string.IsNullOrEmpty(titleKey))
                throw new ArgumentException("Title key must be nonempty.", nameof(titleKey));
            if (bodyKey == null)
                throw new ArgumentNullException(nameof(bodyKey));
            if (expiryUtcTicks < 0)
                throw new ArgumentOutOfRangeException(nameof(expiryUtcTicks), "Expiry must be a valid UTC tick count.");

            MailId = mailId;
            TitleKey = titleKey;
            BodyKey = bodyKey;
            Reward = reward ?? MetaRewardBundle.Empty;
            ExpiryUtcTicks = expiryUtcTicks;
        }

        /// <summary>Expiry as a <see cref="DateTime"/>; MinValue means never expires.</summary>
        public DateTime ExpiryUtc
        {
            get { return new DateTime(ExpiryUtcTicks, DateTimeKind.Utc); }
        }

        /// <summary>True when nowUtc is at or past the expiry instant (expiry 0 = never).</summary>
        public bool IsExpired(long nowUtcTicks)
        {
            if (ExpiryUtcTicks == 0)
                return false;
            return nowUtcTicks >= ExpiryUtcTicks;
        }

        /// <summary>
        /// Atomically claims attached rewards once. Rejects when already
        /// claimed, deleted, or expired relative to <paramref name="nowUtcTicks"/>.
        /// </summary>
        public bool TryClaim(long nowUtcTicks, out MetaRewardBundle reward)
        {
            reward = null;
            if (Claimed || Deleted || IsExpired(nowUtcTicks))
                return false;
            Claimed = true;
            reward = Reward;
            return true;
        }
    }

    /// <summary>
    /// Ordered inbox of mail messages with deterministic prune semantics.
    /// Duplicate mail IDs are rejected on delivery.
    /// </summary>
    public sealed class MetaMailbox
    {
        readonly List<MetaMailMessage> mail = new List<MetaMailMessage>();
        readonly Dictionary<string, MetaMailMessage> byId =
            new Dictionary<string, MetaMailMessage>(StringComparer.Ordinal);

        /// <summary>Current inbox contents in delivery order.</summary>
        public IReadOnlyList<MetaMailMessage> Mail
        {
            get { return mail; }
        }

        public void Deliver(MetaMailMessage message)
        {
            if (message == null)
                throw new ArgumentNullException(nameof(message));
            if (byId.ContainsKey(message.MailId))
                throw new InvalidOperationException("Duplicate mail ID: " + message.MailId);
            byId.Add(message.MailId, message);
            mail.Add(message);
        }

        public bool TryGet(string mailId, out MetaMailMessage message)
        {
            return byId.TryGetValue(mailId, out message);
        }

        public bool TryClaim(string mailId, long nowUtcTicks, out MetaRewardBundle reward)
        {
            MetaMailMessage message;
            reward = null;
            if (!byId.TryGetValue(mailId, out message))
                return false;
            return message.TryClaim(nowUtcTicks, out reward);
        }

        /// <summary>Marks a message deleted (soft delete; stays in the inbox until pruned).</summary>
        public bool Delete(string mailId)
        {
            MetaMailMessage message;
            if (!byId.TryGetValue(mailId, out message) || message.Deleted)
                return false;
            message.Deleted = true;
            return true;
        }

        /// <summary>
        /// Deterministically removes expired and deleted entries, preserving
        /// the delivery order of everything else. Returns the removed count.
        /// </summary>
        public int Prune(long nowUtcTicks)
        {
            int removed = 0;
            for (int i = mail.Count - 1; i >= 0; i--)
            {
                MetaMailMessage message = mail[i];
                if (message.Deleted || message.IsExpired(nowUtcTicks))
                {
                    mail.RemoveAt(i);
                    byId.Remove(message.MailId);
                    removed++;
                }
            }
            return removed;
        }
    }
}
