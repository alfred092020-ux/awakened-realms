using System;
using System.Collections.Generic;

namespace AwakenedRealm.EquipmentV2
{
    /// <summary>
    /// Deterministic equipment definition catalog. Definitions are indexed by
    /// stable ID; validation rejects duplicates and malformed entries.
    /// </summary>
    public sealed class EquipmentCatalog
    {
        readonly List<EquipmentDefinition> _definitions = new List<EquipmentDefinition>();
        readonly Dictionary<string, EquipmentDefinition> _byId = new Dictionary<string, EquipmentDefinition>(StringComparer.Ordinal);

        public EquipmentCatalog() { }

        public EquipmentCatalog(IEnumerable<EquipmentDefinition> definitions)
        {
            if (definitions != null)
                foreach (EquipmentDefinition def in definitions)
                    Add(def);
        }

        /// <summary>Adds a definition; throws on duplicate IDs or invalid data.</summary>
        public void Add(EquipmentDefinition definition)
        {
            ValidateDefinition(definition);
            if (_byId.ContainsKey(definition.DefinitionId))
                throw new InvalidOperationException("Duplicate equipment definition ID: " + definition.DefinitionId);
            _byId[definition.DefinitionId] = definition;
            _definitions.Add(definition);
        }

        public bool TryAdd(EquipmentDefinition definition)
        {
            try
            {
                Add(definition);
                return true;
            }
            catch (ArgumentException)
            {
                return false;
            }
            catch (InvalidOperationException)
            {
                return false;
            }
        }

        public EquipmentDefinition Find(string definitionId)
        {
            EquipmentDefinition def;
            return definitionId != null && _byId.TryGetValue(definitionId, out def) ? def : null;
        }

        public IReadOnlyList<EquipmentDefinition> Definitions
        {
            get { return _definitions; }
        }

        public int Count
        {
            get { return _definitions.Count; }
        }

        public static void ValidateDefinition(EquipmentDefinition definition)
        {
            if (definition == null)
                throw new ArgumentNullException(nameof(definition));
            if (string.IsNullOrWhiteSpace(definition.DefinitionId))
                throw new ArgumentException("Definition ID is required.", nameof(definition));
            if (!Enum.IsDefined(typeof(EquipmentSlot), definition.Slot))
                throw new ArgumentException("Unknown slot.", nameof(definition));
            if (!Enum.IsDefined(typeof(EquipmentRarity), definition.Rarity))
                throw new ArgumentException("Unknown rarity.", nameof(definition));
            if (definition.LevelRequirement < 1)
                throw new ArgumentException("Level requirement must be >= 1.", nameof(definition));
            if (definition.BaseStats == null)
                throw new ArgumentException("BaseStats list must not be null.", nameof(definition));

            var seenStats = new HashSet<EquipmentStatType>();
            for (int i = 0; i < definition.BaseStats.Count; i++)
            {
                StatModifier mod = definition.BaseStats[i];
                if (!Enum.IsDefined(typeof(EquipmentStatType), mod.Stat))
                    throw new ArgumentException("Unknown stat type on definition " + definition.DefinitionId);
                if (mod.Flat < 0f || mod.Percent < 0f)
                    throw new ArgumentException("Negative stat value on definition " + definition.DefinitionId);
                if (!seenStats.Add(mod.Stat))
                    throw new ArgumentException("Duplicate stat " + mod.Stat + " on definition " + definition.DefinitionId);
            }

            if (!string.IsNullOrEmpty(definition.SetId) && EquipmentSetBonuses.Find(definition.SetId) == null)
                throw new ArgumentException("Unknown set ID '" + definition.SetId + "' on definition " + definition.DefinitionId);
        }

        /// <summary>Validates every entry in the catalog.</summary>
        public void ValidateAll()
        {
            for (int i = 0; i < _definitions.Count; i++)
                ValidateDefinition(_definitions[i]);
        }

        /// <summary>
        /// Default starter catalog: one item per slot per rarity (24 items)
        /// across three coherent sets matching the fantasy/anime tone.
        /// </summary>
        public static EquipmentCatalog CreateDefault()
        {
            var catalog = new EquipmentCatalog();

            // Rare (dawnbreak set: weapon/armor/accessory; warden: helmet; arcaneflow: relic; boots unaffiliated flavor)
            catalog.Add(new EquipmentDefinition("eq_r_wpn_dawnsword", "Dawnblade of the Squire", EquipmentSlot.Weapon, EquipmentRarity.Rare, 1, "set_dawnbreak",
                StatModifier.FlatOf(EquipmentStatType.ATK, 40f)));
            catalog.Add(new EquipmentDefinition("eq_r_hlm_wardenhelm", "Warden's Oath Helm", EquipmentSlot.Helmet, EquipmentRarity.Rare, 1, "set_warden",
                StatModifier.FlatOf(EquipmentStatType.HP, 300f), StatModifier.FlatOf(EquipmentStatType.DEF, 15f)));
            catalog.Add(new EquipmentDefinition("eq_r_arm_dawnplate", "Dawnplate Hauberk", EquipmentSlot.Armor, EquipmentRarity.Rare, 1, "set_dawnbreak",
                StatModifier.FlatOf(EquipmentStatType.DEF, 25f)));
            catalog.Add(new EquipmentDefinition("eq_r_bts_swift", "Swiftstride Boots", EquipmentSlot.Boots, EquipmentRarity.Rare, 1, null,
                StatModifier.FlatOf(EquipmentStatType.SPD, 10f)));
            catalog.Add(new EquipmentDefinition("eq_r_acc_dawncharm", "Dawnlight Charm", EquipmentSlot.Accessory, EquipmentRarity.Rare, 1, "set_dawnbreak",
                StatModifier.FlatOf(EquipmentStatType.CritRate, 0.04f)));
            catalog.Add(new EquipmentDefinition("eq_r_rel_arcanegem", "Arcane Ember Gem", EquipmentSlot.Relic, EquipmentRarity.Rare, 1, "set_arcaneflow",
                StatModifier.FlatOf(EquipmentStatType.MAG, 35f)));

            // Epic (warden set emphasis + arcaneflow pair)
            catalog.Add(new EquipmentDefinition("eq_e_wpn_wardenedge", "Warden's Runic Edge", EquipmentSlot.Weapon, EquipmentRarity.Epic, 10, "set_warden",
                StatModifier.FlatOf(EquipmentStatType.ATK, 95f), StatModifier.FlatOf(EquipmentStatType.DEF, 10f)));
            catalog.Add(new EquipmentDefinition("eq_e_hlm_arcanecrown", "Crown of Arcane Flow", EquipmentSlot.Helmet, EquipmentRarity.Epic, 10, "set_arcaneflow",
                StatModifier.FlatOf(EquipmentStatType.HP, 650f), StatModifier.FlatOf(EquipmentStatType.MAG, 20f)));
            catalog.Add(new EquipmentDefinition("eq_e_arm_wardenplate", "Warden's Bulwark Plate", EquipmentSlot.Armor, EquipmentRarity.Epic, 10, "set_warden",
                StatModifier.FlatOf(EquipmentStatType.DEF, 60f), StatModifier.FlatOf(EquipmentStatType.HP, 400f)));
            catalog.Add(new EquipmentDefinition("eq_e_bts_arcanetreads", "Treads of the Veil", EquipmentSlot.Boots, EquipmentRarity.Epic, 10, "set_arcaneflow",
                StatModifier.FlatOf(EquipmentStatType.SPD, 22f), StatModifier.FlatOf(EquipmentStatType.MAG, 15f)));
            catalog.Add(new EquipmentDefinition("eq_e_acc_wardensigil", "Sigil of the Iron Warden", EquipmentSlot.Accessory, EquipmentRarity.Epic, 10, "set_warden",
                StatModifier.FlatOf(EquipmentStatType.Resistance, 0.06f)));
            catalog.Add(new EquipmentDefinition("eq_e_rel_dawnrelic", "Relic of First Light", EquipmentSlot.Relic, EquipmentRarity.Epic, 10, "set_dawnbreak",
                StatModifier.FlatOf(EquipmentStatType.ATK, 60f), StatModifier.FlatOf(EquipmentStatType.CritRate, 0.03f)));

            // Legendary (arcaneflow set emphasis)
            catalog.Add(new EquipmentDefinition("eq_l_wpn_arcanestaff", "Staff of the Ninth Sky", EquipmentSlot.Weapon, EquipmentRarity.Legendary, 25, "set_arcaneflow",
                new StatModifier(EquipmentStatType.MAG, 180f, 0.05f)));
            catalog.Add(new EquipmentDefinition("eq_l_hlm_dawncrown", "Crown of the Dawnbreaker", EquipmentSlot.Helmet, EquipmentRarity.Legendary, 25, "set_dawnbreak",
                StatModifier.FlatOf(EquipmentStatType.HP, 1400f), StatModifier.PercentOf(EquipmentStatType.ATK, 0.04f)));
            catalog.Add(new EquipmentDefinition("eq_l_arm_arcanemail", "Arcaneweave Mail", EquipmentSlot.Armor, EquipmentRarity.Legendary, 25, "set_arcaneflow",
                StatModifier.FlatOf(EquipmentStatType.DEF, 120f), StatModifier.FlatOf(EquipmentStatType.Resistance, 0.08f)));
            catalog.Add(new EquipmentDefinition("eq_l_bts_dawngreaves", "Greaves of the Morning Star", EquipmentSlot.Boots, EquipmentRarity.Legendary, 25, "set_dawnbreak",
                StatModifier.FlatOf(EquipmentStatType.SPD, 40f), StatModifier.FlatOf(EquipmentStatType.ATK, 40f)));
            catalog.Add(new EquipmentDefinition("eq_l_acc_arcaneeye", "Eye of the Arcane Seer", EquipmentSlot.Accessory, EquipmentRarity.Legendary, 25, "set_arcaneflow",
                StatModifier.FlatOf(EquipmentStatType.CritRate, 0.10f)));
            catalog.Add(new EquipmentDefinition("eq_l_rel_wardenaegis", "Aegis of the Eternal Warden", EquipmentSlot.Relic, EquipmentRarity.Legendary, 25, "set_warden",
                StatModifier.FlatOf(EquipmentStatType.HP, 900f), StatModifier.FlatOf(EquipmentStatType.Resistance, 0.10f)));

            // Mythic (mixed apex pieces across all three sets)
            catalog.Add(new EquipmentDefinition("eq_m_wpn_starfang", "Starfang, Blade of the Awakened", EquipmentSlot.Weapon, EquipmentRarity.Mythic, 40, "set_dawnbreak",
                StatModifier.FlatOf(EquipmentStatType.ATK, 320f), StatModifier.PercentOf(EquipmentStatType.CritRate, 0.08f)));
            catalog.Add(new EquipmentDefinition("eq_m_hlm_voidvisage", "Visage of the Hollow Moon", EquipmentSlot.Helmet, EquipmentRarity.Mythic, 40, "set_arcaneflow",
                StatModifier.FlatOf(EquipmentStatType.HP, 2600f), StatModifier.PercentOf(EquipmentStatType.MAG, 0.10f)));
            catalog.Add(new EquipmentDefinition("eq_m_arm_aegisward", "Wardplate of the Last Bastion", EquipmentSlot.Armor, EquipmentRarity.Mythic, 40, "set_warden",
                StatModifier.FlatOf(EquipmentStatType.DEF, 240f), StatModifier.PercentOf(EquipmentStatType.HP, 0.12f)));
            catalog.Add(new EquipmentDefinition("eq_m_bts_galestep", "Galestep Sabatons", EquipmentSlot.Boots, EquipmentRarity.Mythic, 40, "set_dawnbreak",
                StatModifier.FlatOf(EquipmentStatType.SPD, 70f), StatModifier.FlatOf(EquipmentStatType.ATK, 80f)));
            catalog.Add(new EquipmentDefinition("eq_m_acc_eternalband", "Band of the Eternal Vow", EquipmentSlot.Accessory, EquipmentRarity.Mythic, 40, "set_warden",
                StatModifier.FlatOf(EquipmentStatType.Resistance, 0.15f), StatModifier.FlatOf(EquipmentStatType.HP, 800f)));
            catalog.Add(new EquipmentDefinition("eq_m_rel_soulcrystal", "Soulcrystal of the First Flame", EquipmentSlot.Relic, EquipmentRarity.Mythic, 40, "set_arcaneflow",
                StatModifier.FlatOf(EquipmentStatType.MAG, 300f), StatModifier.FlatOf(EquipmentStatType.Resistance, 0.08f)));

            catalog.ValidateAll();
            return catalog;
        }
    }
}
