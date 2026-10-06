using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;

namespace AwakenedRealm.CombatV2
{
    /// <summary>
    /// Immutable hero kit: stable id, display identity, role, range style,
    /// scaling stat, and exactly four abilities in slot order.
    /// </summary>
    public sealed class HeroKit
    {
        public readonly string Id;
        public readonly string DisplayName;
        public readonly string Rarity;
        public readonly HeroRole Role;
        public readonly RangeStyle Range;
        public readonly ScalingStat Scaling;
        public readonly IReadOnlyList<AbilityDefinition> Abilities;

        public HeroKit(
            string id,
            string displayName,
            string rarity,
            HeroRole role,
            RangeStyle range,
            ScalingStat scaling,
            IReadOnlyList<AbilityDefinition> abilities)
        {
            if (string.IsNullOrWhiteSpace(id))
                throw new ArgumentException("Hero id is required.", nameof(id));
            if (string.IsNullOrWhiteSpace(displayName))
                throw new ArgumentException("Display name is required.", nameof(displayName));
            if (abilities == null || abilities.Count != 4)
                throw new ArgumentException("Hero must have exactly four abilities.", nameof(abilities));

            Id = id;
            DisplayName = displayName;
            Rarity = rarity;
            Role = role;
            Range = range;
            Scaling = scaling;
            Abilities = new ReadOnlyCollection<AbilityDefinition>(abilities.ToList());
        }

        public AbilityDefinition GetAbility(AbilitySlot slot)
        {
            for (int i = 0; i < Abilities.Count; i++)
            {
                if (Abilities[i].Slot == slot)
                    return Abilities[i];
            }
            throw new InvalidOperationException("Missing ability slot " + slot + " on hero " + Id);
        }
    }

    /// <summary>
    /// Read-only catalog of all 12 canon hero kits keyed by stable normalized
    /// ids. Constructed once at type initialization; pure data with no Unity
    /// or persistence dependency.
    /// </summary>
    public static class HeroKitCatalog
    {
        static readonly IReadOnlyDictionary<string, HeroKit> ById;
        static readonly IReadOnlyList<HeroKit> Ordered;

        static HeroKitCatalog()
        {
            var kits = new List<HeroKit>
            {
                // ---- DPS ----
                new HeroKit(
                    id: "akira-flamesong",
                    displayName: "Akira Flamesong",
                    rarity: "Mythic",
                    role: HeroRole.Dps,
                    range: RangeStyle.Long,
                    scaling: ScalingStat.Magic,
                    abilities: new[]
                    {
                        new AbilityDefinition("basic", "Blazing Bolt", AbilitySlot.Basic, TargetPattern.SingleEnemy, ScalingStat.Magic, damageCoefficient: 1.10f),
                        new AbilityDefinition("skill", "Inferno Burst", AbilitySlot.Skill, TargetPattern.AllEnemies, ScalingStat.Magic, damageCoefficient: 0.90f,
                            statuses: new[] { new StatusPayload(StatusType.Burn, procChance: 0.20f, durationTurns: 2) }),
                        new AbilityDefinition("passive", "Flameheart", AbilitySlot.Passive, TargetPattern.Self, ScalingStat.Magic,
                            notes: "+10% MAG, immune to first Burn applied to Akira"),
                        new AbilityDefinition("ultimate", "Solar Reign", AbilitySlot.Ultimate, TargetPattern.AllEnemies, ScalingStat.Magic, damageCoefficient: 2.00f,
                            statuses: new[] { new StatusPayload(StatusType.Burn, procChance: 1f, durationTurns: 3) })
                    }),

                new HeroKit(
                    id: "ryuji-stormfang",
                    displayName: "Ryuji Stormfang",
                    rarity: "Legendary",
                    role: HeroRole.Dps,
                    range: RangeStyle.Melee,
                    scaling: ScalingStat.Attack,
                    abilities: new[]
                    {
                        new AbilityDefinition("basic", "Storm Slash", AbilitySlot.Basic, TargetPattern.SingleEnemy, ScalingStat.Attack, damageCoefficient: 1.20f),
                        new AbilityDefinition("skill", "Thunder Fang", AbilitySlot.Skill, TargetPattern.SingleEnemy, ScalingStat.Attack, damageCoefficient: 1.50f,
                            statuses: new[] { new StatusPayload(StatusType.Stun, procChance: 0.25f, durationTurns: 1) }),
                        new AbilityDefinition("passive", "Storm Focus", AbilitySlot.Passive, TargetPattern.Self, ScalingStat.Attack,
                            notes: "+15% Crit chance"),
                        new AbilityDefinition("ultimate", "Tempest Strike", AbilitySlot.Ultimate, TargetPattern.AdjacentEnemies, ScalingStat.Attack,
                            damageCoefficient: 3.00f, splashCoefficient: 0.50f,
                            notes: "300% ATK to main target plus 50% splash to adjacent enemies")
                    }),

                new HeroKit(
                    id: "hikari-moonveil",
                    displayName: "Hikari Moonveil",
                    rarity: "Epic",
                    role: HeroRole.Dps,
                    range: RangeStyle.Long,
                    scaling: ScalingStat.Magic,
                    abilities: new[]
                    {
                        new AbilityDefinition("basic", "Moonbeam", AbilitySlot.Basic, TargetPattern.SingleEnemy, ScalingStat.Magic, damageCoefficient: 1.00f),
                        new AbilityDefinition("skill", "Lunar Pierce", AbilitySlot.Skill, TargetPattern.SingleEnemy, ScalingStat.Magic, damageCoefficient: 1.20f,
                            pierceCount: 3),
                        new AbilityDefinition("passive", "Moonlit Step", AbilitySlot.Passive, TargetPattern.Self, ScalingStat.Magic,
                            notes: "+8% SPD, +5% MAG"),
                        new AbilityDefinition("ultimate", "Eclipse Veil", AbilitySlot.Ultimate, TargetPattern.AllEnemies, ScalingStat.Magic, damageCoefficient: 1.50f,
                            statuses: new[] { new StatusPayload(StatusType.SpeedDown, procChance: 1f, durationTurns: 2) },
                            notes: "-15% SPD to all enemies for 2 turns")
                    }),

                new HeroKit(
                    id: "kenji-ironclaw",
                    displayName: "Kenji Ironclaw",
                    rarity: "Rare",
                    role: HeroRole.Dps,
                    range: RangeStyle.Melee,
                    scaling: ScalingStat.Attack,
                    abilities: new[]
                    {
                        new AbilityDefinition("basic", "Iron Slash", AbilitySlot.Basic, TargetPattern.SingleEnemy, ScalingStat.Attack, damageCoefficient: 1.10f),
                        new AbilityDefinition("skill", "Rending Claw", AbilitySlot.Skill, TargetPattern.SingleEnemy, ScalingStat.Attack, damageCoefficient: 1.40f,
                            statuses: new[] { new StatusPayload(StatusType.Bleed, procChance: 0.10f, durationTurns: 2) }),
                        new AbilityDefinition("passive", "Predator Focus", AbilitySlot.Passive, TargetPattern.Self, ScalingStat.Attack,
                            notes: "+5% Crit chance"),
                        new AbilityDefinition("ultimate", "Execution Pounce", AbilitySlot.Ultimate, TargetPattern.LowestHealthEnemy, ScalingStat.Attack,
                            damageCoefficient: 2.00f, guaranteedCrit: true)
                    }),

                // ---- Support ----
                new HeroKit(
                    id: "ayaka-starbloom",
                    displayName: "Ayaka Starbloom",
                    rarity: "Mythic",
                    role: HeroRole.Support,
                    range: RangeStyle.Long,
                    scaling: ScalingStat.Magic,
                    abilities: new[]
                    {
                        new AbilityDefinition("basic", "Starlight Mend", AbilitySlot.Basic, TargetPattern.LowestHealthAlly, ScalingStat.Magic, healCoefficient: 0.10f),
                        new AbilityDefinition("skill", "Bloom Ward", AbilitySlot.Skill, TargetPattern.AllAllies, ScalingStat.Magic, healCoefficient: 0.60f,
                            statuses: new[] { new StatusPayload(StatusType.DefenseUp, procChance: 1f, durationTurns: 2, magnitudeOverridePercent: 10f) },
                            notes: "+10% DEF for 2 turns"),
                        new AbilityDefinition("passive", "Stellar Grace", AbilitySlot.Passive, TargetPattern.AllAllies, ScalingStat.Magic,
                            notes: "+15% RES to all allies"),
                        new AbilityDefinition("ultimate", "Celestial Bloom", AbilitySlot.Ultimate, TargetPattern.AllAllies, ScalingStat.Magic, healCoefficient: 1.00f,
                            cleansesDebuffs: true)
                    }),

                new HeroKit(
                    id: "haruto-sagewind",
                    displayName: "Haruto Sagewind",
                    rarity: "Legendary",
                    role: HeroRole.Support,
                    range: RangeStyle.Long,
                    scaling: ScalingStat.Magic,
                    abilities: new[]
                    {
                        new AbilityDefinition("basic", "Wind Sigil", AbilitySlot.Basic, TargetPattern.SingleEnemy, ScalingStat.Magic, damageCoefficient: 0.90f),
                        new AbilityDefinition("skill", "Tailwind", AbilitySlot.Skill, TargetPattern.AllAllies, ScalingStat.Magic,
                            statuses: new[]
                            {
                                new StatusPayload(StatusType.SpeedUp, procChance: 1f, durationTurns: 2),
                                new StatusPayload(StatusType.AttackUp, procChance: 1f, durationTurns: 2, magnitudeOverridePercent: 10f)
                            }),
                        new AbilityDefinition("passive", "Zephyr Aura", AbilitySlot.Passive, TargetPattern.AllAllies, ScalingStat.Magic,
                            notes: "+5% SPD to all allies"),
                        new AbilityDefinition("ultimate", "Sagewind Ascension", AbilitySlot.Ultimate, TargetPattern.AllAllies, ScalingStat.Magic,
                            statuses: new[] { new StatusPayload(StatusType.AttackUp, procChance: 1f, durationTurns: 2, magnitudeOverridePercent: 25f) },
                            grantsExtraTurn: true,
                            notes: "+25% ATK to all allies and grants one extra turn to DPS heroes")
                    }),

                new HeroKit(
                    id: "mika-lyrica",
                    displayName: "Mika Lyrica",
                    rarity: "Epic",
                    role: HeroRole.Support,
                    range: RangeStyle.Long,
                    scaling: ScalingStat.Magic,
                    abilities: new[]
                    {
                        new AbilityDefinition("basic", "Dissonant Note", AbilitySlot.Basic, TargetPattern.SingleEnemy, ScalingStat.Magic, damageCoefficient: 0.85f),
                        new AbilityDefinition("skill", "Harmonic Chord", AbilitySlot.Skill, TargetPattern.AllAllies, ScalingStat.Magic,
                            statuses: new[]
                            {
                                new StatusPayload(StatusType.AttackUp, procChance: 1f, durationTurns: 3, magnitudeOverridePercent: 10f),
                                new StatusPayload(StatusType.MagicUp, procChance: 1f, durationTurns: 3, magnitudeOverridePercent: 10f)
                            }),
                        new AbilityDefinition("passive", "Resonance", AbilitySlot.Passive, TargetPattern.AllAllies, ScalingStat.Magic,
                            notes: "+5% DEF to all allies"),
                        new AbilityDefinition("ultimate", "Crescendo Finale", AbilitySlot.Ultimate, TargetPattern.AllEnemies, ScalingStat.Magic,
                            damageCoefficient: 1.20f, healFromDamageDealtPercent: 0.50f,
                            notes: "120% MAG to all enemies, heals allies for 50% of damage dealt")
                    }),

                new HeroKit(
                    id: "sora-willowheart",
                    displayName: "Sora Willowheart",
                    rarity: "Rare",
                    role: HeroRole.Support,
                    range: RangeStyle.Long,
                    scaling: ScalingStat.Magic,
                    abilities: new[]
                    {
                        new AbilityDefinition("basic", "Thorn Whip", AbilitySlot.Basic, TargetPattern.SingleEnemy, ScalingStat.Magic, damageCoefficient: 0.85f,
                            statuses: new[] { new StatusPayload(StatusType.Root, procChance: 0.10f, durationTurns: 1) }),
                        new AbilityDefinition("skill", "Willow Snare", AbilitySlot.Skill, TargetPattern.AllEnemies, ScalingStat.Magic,
                            statuses: new[] { new StatusPayload(StatusType.SpeedDown, procChance: 1f, durationTurns: 2) }),
                        new AbilityDefinition("passive", "Barkskin Ward", AbilitySlot.Passive, TargetPattern.AllAllies, ScalingStat.Magic,
                            notes: "+3% RES to all allies"),
                        new AbilityDefinition("ultimate", "Nature's Grasp", AbilitySlot.Ultimate, TargetPattern.AllEnemies, ScalingStat.Magic,
                            damageCoefficient: 1.00f,
                            statuses: new[] { new StatusPayload(StatusType.AttackDown, procChance: 1f, durationTurns: 2, magnitudeOverridePercent: -10f) })
                    }),

                // ---- Defenders ----
                new HeroKit(
                    id: "raiden-kurogane",
                    displayName: "Raiden Kurogane",
                    rarity: "Mythic",
                    role: HeroRole.Defender,
                    range: RangeStyle.Melee,
                    scaling: ScalingStat.Attack,
                    abilities: new[]
                    {
                        new AbilityDefinition("basic", "Kurogane Bash", AbilitySlot.Basic, TargetPattern.SingleEnemy, ScalingStat.Attack, damageCoefficient: 1.00f),
                        new AbilityDefinition("skill", "Iron Taunt", AbilitySlot.Skill, TargetPattern.AllEnemies, ScalingStat.Attack,
                            statuses: new[]
                            {
                                new StatusPayload(StatusType.Taunt, procChance: 1f, durationTurns: 2),
                                new StatusPayload(StatusType.DefenseUp, procChance: 1f, durationTurns: 2, magnitudeOverridePercent: 30f, applyToCasterSide: true)
                            },
                            notes: "Taunt all enemies and grant self +30% DEF for 2 turns"),
                        new AbilityDefinition("passive", "Unyielding", AbilitySlot.Passive, TargetPattern.Self, ScalingStat.Attack,
                            notes: "Immune to first Stun"),
                        new AbilityDefinition("ultimate", "Aegis of the Iron Mountain", AbilitySlot.Ultimate, TargetPattern.AllAllies, ScalingStat.MaxHealth,
                            shieldFromMaxHealthPercent: 0.40f,
                            notes: "Shield all allies for 40% of Raiden's max HP for 3 turns")
                    }),

                new HeroKit(
                    id: "takeshi-stonefist",
                    displayName: "Takeshi Stonefist",
                    rarity: "Legendary",
                    role: HeroRole.Defender,
                    range: RangeStyle.Melee,
                    scaling: ScalingStat.Attack,
                    abilities: new[]
                    {
                        new AbilityDefinition("basic", "Stone Jab", AbilitySlot.Basic, TargetPattern.SingleEnemy, ScalingStat.Attack, damageCoefficient: 1.10f),
                        new AbilityDefinition("skill", "Seismic Slam", AbilitySlot.Skill, TargetPattern.AllEnemies, ScalingStat.Attack, damageCoefficient: 1.30f,
                            statuses: new[] { new StatusPayload(StatusType.Stun, procChance: 0.20f, durationTurns: 1) }),
                        new AbilityDefinition("passive", "Stoneskin", AbilitySlot.Passive, TargetPattern.Self, ScalingStat.Attack,
                            notes: "+10% DEF to self"),
                        new AbilityDefinition("ultimate", "Quake Fist", AbilitySlot.Ultimate, TargetPattern.AllEnemies, ScalingStat.Attack, damageCoefficient: 2.00f,
                            statuses: new[] { new StatusPayload(StatusType.DefenseDown, procChance: 1f, durationTurns: 2, magnitudeOverridePercent: -15f) })
                    }),

                new HeroKit(
                    id: "kaoru-steelheart",
                    displayName: "Kaoru Steelheart",
                    rarity: "Epic",
                    role: HeroRole.Defender,
                    range: RangeStyle.Melee,
                    scaling: ScalingStat.Attack,
                    abilities: new[]
                    {
                        new AbilityDefinition("basic", "Steel Cut", AbilitySlot.Basic, TargetPattern.SingleEnemy, ScalingStat.Attack, damageCoefficient: 1.00f,
                            statuses: new[] { new StatusPayload(StatusType.Stun, procChance: 0.05f, durationTurns: 1) }),
                        new AbilityDefinition("skill", "Bulwark Stance", AbilitySlot.Skill, TargetPattern.Self, ScalingStat.Attack,
                            statuses: new[]
                            {
                                new StatusPayload(StatusType.DefenseUp, procChance: 1f, durationTurns: 2, magnitudeOverridePercent: 25f),
                                new StatusPayload(StatusType.ResistanceUp, procChance: 1f, durationTurns: 2, magnitudeOverridePercent: 15f)
                            }),
                        new AbilityDefinition("passive", "Steel Lattice", AbilitySlot.Passive, TargetPattern.AllAllies, ScalingStat.Attack,
                            notes: "+3% DEF to all allies"),
                        new AbilityDefinition("ultimate", "Rampart Shield", AbilitySlot.Ultimate, TargetPattern.AllAllies, ScalingStat.MaxHealth,
                            shieldFromMaxHealthPercent: 0.20f,
                            notes: "Shield all allies for 20% of Kaoru's max HP for 2 turns")
                    }),

                new HeroKit(
                    id: "hiroshi-boulderback",
                    displayName: "Hiroshi Boulderback",
                    rarity: "Rare",
                    role: HeroRole.Defender,
                    range: RangeStyle.Melee,
                    scaling: ScalingStat.Attack,
                    abilities: new[]
                    {
                        new AbilityDefinition("basic", "Boulder Bash", AbilitySlot.Basic, TargetPattern.SingleEnemy, ScalingStat.Attack, damageCoefficient: 0.95f),
                        new AbilityDefinition("skill", "Pebble Toss", AbilitySlot.Skill, TargetPattern.SingleEnemy, ScalingStat.Attack,
                            statuses: new[] { new StatusPayload(StatusType.Taunt, procChance: 1f, durationTurns: 1) },
                            notes: "Taunt 2 enemies for 1 turn"),
                        new AbilityDefinition("passive", "Thick Hide", AbilitySlot.Passive, TargetPattern.Self, ScalingStat.Attack,
                            notes: "+5% HP to self"),
                        new AbilityDefinition("ultimate", "Sheltering Crag", AbilitySlot.Ultimate, TargetPattern.LowestHealthAlly, ScalingStat.Defense,
                            shieldFromDefensePercent: 0.50f,
                            notes: "Shield lowest-HP ally for 50% of Hiroshi's DEF for 2 turns")
                    })
            };

            var ordered = kits.OrderBy(k => k.Id, StringComparer.Ordinal).ToList();
            var dict = new Dictionary<string, HeroKit>(StringComparer.Ordinal);
            foreach (var kit in ordered)
            {
                if (dict.ContainsKey(kit.Id))
                    throw new InvalidOperationException("Duplicate hero kit id " + kit.Id);
                dict.Add(kit.Id, kit);
            }

            Ordered = new ReadOnlyCollection<HeroKit>(ordered);
            ById = new ReadOnlyDictionary<string, HeroKit>(dict);
        }

        public static IReadOnlyList<HeroKit> All
        {
            get { return Ordered; }
        }

        public static int Count
        {
            get { return Ordered.Count; }
        }

        public static HeroKit Get(string id)
        {
            HeroKit kit;
            if (ById.TryGetValue(id, out kit))
                return kit;
            throw new ArgumentException("Unknown hero kit id: " + id, nameof(id));
        }

        public static bool TryGet(string id, out HeroKit kit)
        {
            return ById.TryGetValue(id, out kit);
        }

        public static bool Contains(string id)
        {
            return ById.ContainsKey(id);
        }
    }
}
