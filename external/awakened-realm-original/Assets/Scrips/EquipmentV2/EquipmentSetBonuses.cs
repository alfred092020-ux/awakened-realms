using System;
using System.Collections.Generic;

namespace AwakenedRealm.EquipmentV2
{
    /// <summary>
    /// Deterministic set-bonus definitions and aggregation. Thresholds are fixed
    /// at 2-piece and 4-piece; effect payloads are flat/percent stat modifiers.
    /// </summary>
    public static class EquipmentSetBonuses
    {
        public const int TwoPieceThreshold = 2;
        public const int FourPieceThreshold = 4;

        public sealed class SetBonusDefinition
        {
            public readonly string SetId;
            public readonly StatModifier[] TwoPiece;
            public readonly StatModifier[] FourPiece;

            public SetBonusDefinition(string setId, StatModifier[] twoPiece, StatModifier[] fourPiece)
            {
                if (string.IsNullOrWhiteSpace(setId))
                    throw new ArgumentException("Set ID is required.", nameof(setId));
                SetId = setId;
                TwoPiece = twoPiece ?? new StatModifier[0];
                FourPiece = fourPiece ?? new StatModifier[0];
            }
        }

        static readonly Dictionary<string, SetBonusDefinition> Sets = BuildSets();

        static Dictionary<string, SetBonusDefinition> BuildSets()
        {
            var defs = new List<SetBonusDefinition>
            {
                new SetBonusDefinition(
                    "set_dawnbreak",
                    new[] { StatModifier.PercentOf(EquipmentStatType.ATK, 0.08f) },
                    new[]
                    {
                        StatModifier.PercentOf(EquipmentStatType.ATK, 0.16f),
                        StatModifier.PercentOf(EquipmentStatType.CritRate, 0.10f)
                    }),
                new SetBonusDefinition(
                    "set_warden",
                    new[] { StatModifier.PercentOf(EquipmentStatType.DEF, 0.10f) },
                    new[]
                    {
                        StatModifier.PercentOf(EquipmentStatType.DEF, 0.20f),
                        StatModifier.PercentOf(EquipmentStatType.HP, 0.12f)
                    }),
                new SetBonusDefinition(
                    "set_arcaneflow",
                    new[] { StatModifier.PercentOf(EquipmentStatType.MAG, 0.08f) },
                    new[]
                    {
                        StatModifier.PercentOf(EquipmentStatType.MAG, 0.18f),
                        StatModifier.FlatOf(EquipmentStatType.SPD, 8f)
                    })
            };

            var map = new Dictionary<string, SetBonusDefinition>(StringComparer.Ordinal);
            for (int i = 0; i < defs.Count; i++)
            {
                if (map.ContainsKey(defs[i].SetId))
                    throw new InvalidOperationException("Duplicate set ID: " + defs[i].SetId);
                map[defs[i].SetId] = defs[i];
            }
            return map;
        }

        public static SetBonusDefinition Find(string setId)
        {
            SetBonusDefinition def;
            return setId != null && Sets.TryGetValue(setId, out def) ? def : null;
        }

        public static IEnumerable<SetBonusDefinition> All
        {
            get { return Sets.Values; }
        }

        /// <summary>
        /// Aggregates active set-bonus modifiers for a hero from their equipped
        /// items. Deterministic: counts pieces per set, applies 2pc/4pc payloads.
        /// </summary>
        public static List<StatModifier> AggregateActiveModifiers(
            string heroId,
            EquipmentLoadouts loadouts,
            EquipmentInventory inventory,
            EquipmentCatalog catalog)
        {
            var result = new List<StatModifier>();
            if (loadouts == null || inventory == null || catalog == null)
                return result;

            List<string> equipped = loadouts.EquippedInstances(heroId);
            var setCounts = new Dictionary<string, int>(StringComparer.Ordinal);
            for (int i = 0; i < equipped.Count; i++)
            {
                EquipmentInstance instance = inventory.Find(equipped[i]);
                if (instance == null)
                    continue;
                EquipmentDefinition def = catalog.Find(instance.DefinitionId);
                if (def == null || string.IsNullOrEmpty(def.SetId))
                    continue;
                int count;
                setCounts.TryGetValue(def.SetId, out count);
                setCounts[def.SetId] = count + 1;
            }

            // Deterministic ordering: iterate sets in sorted order.
            var setIds = new List<string>(setCounts.Keys);
            setIds.Sort(StringComparer.Ordinal);
            for (int i = 0; i < setIds.Count; i++)
            {
                SetBonusDefinition setDef = Find(setIds[i]);
                if (setDef == null)
                    continue;
                int pieces = setCounts[setIds[i]];
                if (pieces >= TwoPieceThreshold)
                    result.AddRange(setDef.TwoPiece);
                if (pieces >= FourPieceThreshold)
                    result.AddRange(setDef.FourPiece);
            }
            return result;
        }
    }
}
