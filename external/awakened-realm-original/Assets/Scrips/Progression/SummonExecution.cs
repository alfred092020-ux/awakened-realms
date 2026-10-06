using System;
using System.Collections.Generic;
using AwakenedRealm.Enums;

namespace AwakenedRealm.Progression
{
    /// <summary>
    /// Centralized banner configuration: pull rates, costs, and guarantees.
    /// Rarity probabilities sum to exactly 1 (as scaled integer weights).
    /// </summary>
    public sealed class SummonConfig
    {
        // Probability weights per million; must total WeightScale exactly.
        public const int WeightScale = 1000000;

        // Non-predatory defaults: rare 85%, epic 11.5%, legendary 3%, mythic 0.5%.
        public int RareWeight = 850000;
        public int EpicWeight = 115000;
        public int LegendaryWeight = 30000;
        public int MythicWeight = 5000;

        public int GemCostSingle = 300;
        public int GemCostTenPull = 2700;
        public int TicketCostSingle = 1;
        public int TicketCostTenPull = 10;

        // Base-rate weight multipliers applied during soft pity (x100 = 1.0x).
        public int LegendarySoftWeightScale = 200;
        public int MythicSoftWeightScale = 200;

        public void Validate()
        {
            if (RareWeight < 0 || EpicWeight < 0 || LegendaryWeight < 0 || MythicWeight < 0)
                throw new InvalidOperationException("Summon rarity weights cannot be negative.");
            if ((long)RareWeight + EpicWeight + LegendaryWeight + MythicWeight != WeightScale)
                throw new InvalidOperationException("Summon rarity weights must sum to WeightScale.");
            if (EpicWeight <= 0 || LegendaryWeight <= 0 || MythicWeight <= 0)
                throw new InvalidOperationException("Epic and higher tiers must have positive weight.");
            if (GemCostSingle < 0 || GemCostTenPull < 0 || TicketCostSingle < 0 || TicketCostTenPull < 0)
                throw new InvalidOperationException("Summon costs cannot be negative.");
            if (LegendarySoftWeightScale < 100 || MythicSoftWeightScale < 100)
                throw new InvalidOperationException("Soft pity weight scale cannot reduce base odds below 1x.");

            // Soft-pity boosts are funded by lower tiers, so the combined
            // incremental weight must fit inside the rare+epic budget.
            // Matches the integer math used by RollRarity.
            long boost = ((long)LegendaryWeight * LegendarySoftWeightScale / 100 - LegendaryWeight)
                       + ((long)MythicWeight * MythicSoftWeightScale / 100 - MythicWeight);
            if (boost >= RareWeight + EpicWeight)
                throw new InvalidOperationException("Soft pity weight scaling can consume the whole lower-tier roll range.");
        }
    }

    /// <summary>A pullable hero: stable ID plus its authored rarity.</summary>
    public sealed class SummonPoolEntry
    {
        public string HeroId;
        public HeroRarity Rarity;

        public SummonPoolEntry(string heroId, HeroRarity rarity)
        {
            HeroId = heroId;
            Rarity = rarity;
        }
    }

    /// <summary>Validated hero summon pool. Validation is all-or-nothing.</summary>
    public sealed class SummonHeroPool
    {
        readonly List<SummonPoolEntry> ordered = new List<SummonPoolEntry>();
        readonly Dictionary<HeroRarity, List<SummonPoolEntry>> byRarity =
            new Dictionary<HeroRarity, List<SummonPoolEntry>>();

        public SummonHeroPool(IEnumerable<SummonPoolEntry> entries)
        {
            if (entries == null)
                throw new ArgumentNullException(nameof(entries));

            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (SummonPoolEntry entry in entries)
            {
                if (entry == null || string.IsNullOrWhiteSpace(entry.HeroId))
                    throw new InvalidOperationException("Summon pool contains a hero without a stable ID.");
                if (!seen.Add(entry.HeroId))
                    throw new InvalidOperationException("Summon pool contains duplicate hero ID: " + entry.HeroId);
                if (!IsSupported(entry.Rarity))
                    throw new InvalidOperationException("Summon pool contains unsupported rarity: " + entry.HeroId);

                List<SummonPoolEntry> bucket;
                if (!byRarity.TryGetValue(entry.Rarity, out bucket))
                {
                    bucket = new List<SummonPoolEntry>();
                    byRarity.Add(entry.Rarity, bucket);
                }
                bucket.Add(entry);
                ordered.Add(entry);
            }

            // The pool must be able to satisfy every tier the banner can force.
            RequireTier(HeroRarity.rare);
            RequireTier(HeroRarity.epic);
            RequireTier(HeroRarity.legendary);
            RequireTier(HeroRarity.mythic);
        }

        public static bool IsSupported(HeroRarity rarity)
        {
            return rarity == HeroRarity.rare || rarity == HeroRarity.epic ||
                   rarity == HeroRarity.legendary || rarity == HeroRarity.mythic;
        }

        public bool HasTierOrBetter(HeroRarity minimum)
        {
            for (int i = 0; i < ordered.Count; i++)
                if (ordered[i].Rarity >= minimum)
                    return true;
            return false;
        }

        public List<SummonPoolEntry> Tier(HeroRarity rarity)
        {
            List<SummonPoolEntry> result;
            if (!byRarity.TryGetValue(rarity, out result))
                result = new List<SummonPoolEntry>();
            return result;
        }

        void RequireTier(HeroRarity rarity)
        {
            List<SummonPoolEntry> bucket;
            if (!byRarity.TryGetValue(rarity, out bucket) || bucket.Count == 0)
                throw new InvalidOperationException("Summon pool cannot satisfy tier: " + rarity);
        }
    }

    /// <summary>
    /// Minimal seedable RNG contract. 64-bit draws, deterministic across runtimes.
    /// Never backed by UnityEngine.Random.
    /// </summary>
    public interface IDeterministicRandom
    {
        ulong NextUInt64();
    }

    /// <summary>xorshift64* — deterministic, seedable, zero Unity dependencies.</summary>
    public sealed class XorShift64Random : IDeterministicRandom
    {
        ulong state;

        public XorShift64Random(ulong seed)
        {
            if (seed == 0) seed = 0x9E3779B97F4A7C15UL;
            state = seed;
        }

        public ulong NextUInt64()
        {
            ulong x = state;
            x ^= x >> 12;
            x ^= x << 25;
            x ^= x >> 27;
            state = x;
            return x * 0x2545F4914F6CDD1DUL;
        }
    }

    /// <summary>What funded one summon request.</summary>
    public enum SummonSpendKind
    {
        none,
        tickets,
        gems
    }

    /// <summary>Outcome of a single resolved pull.</summary>
    public sealed class SummonPullResult
    {
        public string HeroId;
        public HeroRarity Rarity;
        public bool IsNew;
        public int ResultingDuplicateCopies;
        public bool PityForced;
    }

    /// <summary>Result of one atomic summon request (single or multi-pull).</summary>
    public sealed class SummonResult
    {
        public List<SummonPullResult> Pulls = new List<SummonPullResult>();
        public SummonSpendKind SpentWith = SummonSpendKind.none;
        public int SpentAmount;
        public bool EpicOrBetterGuaranteed;

        public bool ContainsEpicOrBetter
        {
            get
            {
                for (int i = 0; i < Pulls.Count; i++)
                    if (Pulls[i].Rarity >= HeroRarity.epic)
                        return true;
                return false;
            }
        }
    }

    /// <summary>
    /// Deterministic summon execution. Every request validates first, resolves on a
    /// cloned working state, and commits only when the whole request succeeds, so a
    /// failed pull never partially mutates the roster, wallet, or pity counters.
    /// </summary>
    public static class SummonExecutor
    {
        public const int TenPullCount = 10;

        public static SummonResult SummonSingle(GameProgressionState state, SummonHeroPool pool,
            IDeterministicRandom rng, SummonConfig config = null)
        {
            return Summon(state, pool, rng, config, 1, guaranteeEpicOrBetter: false);
        }

        public static SummonResult SummonTenPull(GameProgressionState state, SummonHeroPool pool,
            IDeterministicRandom rng, SummonConfig config = null)
        {
            return Summon(state, pool, rng, config, TenPullCount, guaranteeEpicOrBetter: true);
        }

        /// <summary>
        /// Resolves a full request atomically. Tickets fund the whole request when
        /// sufficient, otherwise gems fund the whole request; resources never mix.
        /// </summary>
        public static SummonResult Summon(GameProgressionState state, SummonHeroPool pool,
            IDeterministicRandom rng, SummonConfig config, int pullCount, bool guaranteeEpicOrBetter)
        {
            if (state == null) throw new ArgumentNullException(nameof(state));
            if (pool == null) throw new ArgumentNullException(nameof(pool));
            if (rng == null) throw new ArgumentNullException(nameof(rng));
            if (pullCount <= 0)
                throw new ArgumentOutOfRangeException(nameof(pullCount), pullCount, "Pull count must be positive.");
            if (config == null) config = new SummonConfig();
            config.Validate();
            state.Validate();

            if (guaranteeEpicOrBetter && !pool.HasTierOrBetter(HeroRarity.epic))
                throw new InvalidOperationException("Summon pool cannot satisfy the epic-or-better guarantee.");

            int ticketCost = pullCount == 1 ? config.TicketCostSingle
                : pullCount == TenPullCount ? config.TicketCostTenPull
                : pullCount * config.TicketCostSingle;
            int gemCost = pullCount == 1 ? config.GemCostSingle
                : pullCount == TenPullCount ? config.GemCostTenPull
                : pullCount * config.GemCostSingle;

            SummonSpendKind spendKind;
            int spendAmount;
            if (ticketCost == 0)
            {
                spendKind = SummonSpendKind.none;
                spendAmount = 0;
            }
            else if (state.SummonTickets >= ticketCost)
            {
                spendKind = SummonSpendKind.tickets;
                spendAmount = ticketCost;
            }
            else if (gemCost == 0)
            {
                spendKind = SummonSpendKind.none;
                spendAmount = 0;
            }
            else if (state.Gems >= gemCost)
            {
                spendKind = SummonSpendKind.gems;
                spendAmount = gemCost;
            }
            else
            {
                throw new InvalidOperationException("Insufficient resources for summon request.");
            }

            // Resolve on a working copy; commit only after every pull succeeds.
            WorkingState work = WorkingState.From(state);
            var result = new SummonResult
            {
                SpentWith = spendKind,
                SpentAmount = spendAmount,
                EpicOrBetterGuaranteed = guaranteeEpicOrBetter
            };

            // Spending is applied to the working copy so the commit covers
            // roster, pity counters, and wallet in one atomic step.
            work.ApplySpend(spendKind, spendAmount);

            bool guaranteedHitPending = guaranteeEpicOrBetter;
            for (int i = 0; i < pullCount; i++)
            {
                bool forceEpicFloor = guaranteedHitPending && i == pullCount - 1;
                SummonPullResult pull = ResolvePull(work, pool, rng, config, forceEpicFloor);
                result.Pulls.Add(pull);
                if (pull.Rarity >= HeroRarity.epic)
                    guaranteedHitPending = false;
            }

            if (guaranteedHitPending)
                throw new InvalidOperationException("Summon guarantee could not be satisfied.");

            work.CommitTo(state);
            state.Validate();
            return result;
        }

        static SummonPullResult ResolvePull(WorkingState work, SummonHeroPool pool,
            IDeterministicRandom rng, SummonConfig config, bool forceEpicFloor)
        {
            HeroRarity rarity;
            bool pityForced = false;

            // Hard pity forces the tier deterministically when reached.
            if (work.MythicPity == SummoningService.MythicHardPity - 1)
            {
                rarity = HeroRarity.mythic;
                pityForced = true;
            }
            else if (work.LegendaryPity == SummoningService.LegendaryHardPity - 1)
            {
                rarity = HeroRarity.legendary;
                pityForced = true;
            }
            else
            {
                rarity = RollRarity(work, pool, rng, config, forceEpicFloor);
            }

            SummonPoolEntry pick = PickFromTier(work, pool, rng, rarity);
            SummonPullResult pull = Grant(work, pick);
            pull.PityForced = pityForced;
            return pull;
        }

        static HeroRarity RollRarity(WorkingState work, SummonHeroPool pool,
            IDeterministicRandom rng, SummonConfig config, bool forceEpicFloor)
        {
            long legendaryWeight = config.LegendaryWeight;
            long mythicWeight = config.MythicWeight;
            if (work.LegendaryPity >= SummoningService.LegendarySoftPity)
                legendaryWeight = legendaryWeight * config.LegendarySoftWeightScale / 100;
            if (work.MythicPity >= SummoningService.MythicSoftPity)
                mythicWeight = mythicWeight * config.MythicSoftWeightScale / 100;

            // Highest tiers win the roll; soft-pity boosts are funded by lower tiers.
            ulong roll = rng.NextUInt64() % SummonConfig.WeightScale;
            if (roll < (ulong)mythicWeight)
                return HeroRarity.mythic;
            roll -= (ulong)mythicWeight;
            if (roll < (ulong)legendaryWeight)
                return HeroRarity.legendary;

            ulong remaining = roll - (ulong)legendaryWeight;
            if (remaining < (ulong)config.EpicWeight)
                return HeroRarity.epic;
            if (forceEpicFloor)
            {
                // Guarantee fallback: the epic tier still resolves through the pool,
                // so roster records are only ever created once per hero ID.
                return HeroRarity.epic;
            }
            return HeroRarity.rare;
        }

        static SummonPoolEntry PickFromTier(WorkingState work, SummonHeroPool pool,
            IDeterministicRandom rng, HeroRarity rarity)
        {
            List<SummonPoolEntry> candidates = pool.Tier(rarity);
            if (candidates.Count == 0)
                throw new InvalidOperationException("Summon pool has no entries in tier: " + rarity);
            int index = (int)(rng.NextUInt64() % (ulong)candidates.Count);
            return candidates[index];
        }

        static SummonPullResult Grant(WorkingState work, SummonPoolEntry pick)
        {
            OwnedHeroProgression owned = work.Find(pick.HeroId);
            var pull = new SummonPullResult
            {
                HeroId = pick.HeroId,
                Rarity = pick.Rarity
            };

            if (owned == null)
            {
                work.Heroes.Add(new OwnedHeroProgression(pick.HeroId, pick.Rarity));
                pull.IsNew = true;
                pull.ResultingDuplicateCopies = 0;
            }
            else
            {
                owned.DuplicateCopies += 1;
                pull.IsNew = false;
                pull.ResultingDuplicateCopies = owned.DuplicateCopies;
            }

            // Mythic satisfies both pity tracks; legendary resets only its own.
            if (pick.Rarity == HeroRarity.mythic)
            {
                work.LegendaryPity = 0;
                work.MythicPity = 0;
            }
            else if (pick.Rarity == HeroRarity.legendary)
            {
                work.LegendaryPity = 0;
                work.MythicPity += 1;
            }
            else
            {
                work.LegendaryPity += 1;
                work.MythicPity += 1;
            }

            return pull;
        }

        /// <summary>Mutable clone used to prove a request fully resolves before commit.</summary>
        sealed class WorkingState
        {
            public List<OwnedHeroProgression> Heroes;
            public int LegendaryPity;
            public int MythicPity;
            public int SummonTickets;
            public int Gems;

            public static WorkingState From(GameProgressionState state)
            {
                var work = new WorkingState
                {
                    Heroes = new List<OwnedHeroProgression>(state.Heroes.Count),
                    LegendaryPity = state.LegendaryPity,
                    MythicPity = state.MythicPity,
                    SummonTickets = state.SummonTickets,
                    Gems = state.Gems
                };
                for (int i = 0; i < state.Heroes.Count; i++)
                {
                    OwnedHeroProgression hero = state.Heroes[i];
                    work.Heroes.Add(new OwnedHeroProgression
                    {
                        HeroId = hero.HeroId,
                        Rarity = hero.Rarity,
                        Level = hero.Level,
                        Stars = hero.Stars,
                        DuplicateCopies = hero.DuplicateCopies,
                        Fodder = hero.Fodder
                    });
                }
                return work;
            }

            public OwnedHeroProgression Find(string heroId)
            {
                for (int i = 0; i < Heroes.Count; i++)
                    if (string.Equals(Heroes[i].HeroId, heroId, StringComparison.Ordinal))
                        return Heroes[i];
                return null;
            }

            public void ApplySpend(SummonSpendKind kind, int amount)
            {
                switch (kind)
                {
                    case SummonSpendKind.tickets:
                        SummonTickets -= amount;
                        break;
                    case SummonSpendKind.gems:
                        Gems -= amount;
                        break;
                }
            }

            public void CommitTo(GameProgressionState state)
            {
                state.Heroes = Heroes;
                state.LegendaryPity = LegendaryPity;
                state.MythicPity = MythicPity;
                state.SummonTickets = SummonTickets;
                state.Gems = Gems;
            }
        }
    }
}
