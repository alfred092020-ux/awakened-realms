using System;
using System.Collections.Generic;

namespace AwakenedRealm.EquipmentV2
{
    /// <summary>
    /// Per-hero equipment loadouts. One instance per slot per hero; an instance
    /// can only ever be equipped on one hero at a time. Equip/unequip are atomic.
    /// </summary>
    [Serializable]
    public sealed class EquipmentLoadouts
    {
        [Serializable]
        public sealed class HeroLoadout
        {
            public string HeroId;
            // Six entries indexed by EquipmentSlot ordinal; empty = null.
            public string[] SlotInstanceIds = new string[6];

            public HeroLoadout() { }

            public HeroLoadout(string heroId)
            {
                HeroId = heroId;
            }
        }

        public List<HeroLoadout> Heroes = new List<HeroLoadout>();

        // Runtime index: instanceId -> heroId, rebuilt on demand.
        Dictionary<string, string> _equippedByInstance;
        Dictionary<string, HeroLoadout> _byHero;

        static int SlotIndex(EquipmentSlot slot)
        {
            int idx = (int)slot;
            if (idx < 0 || idx >= 6)
                throw new ArgumentOutOfRangeException(nameof(slot));
            return idx;
        }

        void EnsureIndex()
        {
            if (_byHero != null)
                return;

            _byHero = new Dictionary<string, HeroLoadout>(StringComparer.Ordinal);
            _equippedByInstance = new Dictionary<string, string>(StringComparer.Ordinal);
            for (int i = 0; i < Heroes.Count; i++)
            {
                HeroLoadout loadout = Heroes[i];
                if (loadout == null || string.IsNullOrWhiteSpace(loadout.HeroId))
                    throw new InvalidOperationException("Loadout contains an entry without a valid hero ID.");
                if (_byHero.ContainsKey(loadout.HeroId))
                    throw new InvalidOperationException("Duplicate loadout for hero: " + loadout.HeroId);
                _byHero[loadout.HeroId] = loadout;

                for (int s = 0; s < loadout.SlotInstanceIds.Length; s++)
                {
                    string instanceId = loadout.SlotInstanceIds[s];
                    if (string.IsNullOrEmpty(instanceId))
                        continue;
                    if (_equippedByInstance.ContainsKey(instanceId))
                        throw new InvalidOperationException("Instance equipped on two heroes: " + instanceId);
                    _equippedByInstance[instanceId] = loadout.HeroId;
                }
            }
        }

        HeroLoadout GetOrCreateHero(string heroId)
        {
            EnsureIndex();
            HeroLoadout loadout;
            if (_byHero.TryGetValue(heroId, out loadout))
                return loadout;
            loadout = new HeroLoadout(heroId);
            _byHero[heroId] = loadout;
            Heroes.Add(loadout);
            return loadout;
        }

        public bool IsEquipped(string instanceId)
        {
            EnsureIndex();
            return instanceId != null && _equippedByInstance.ContainsKey(instanceId);
        }

        public string EquippedHeroId(string instanceId)
        {
            EnsureIndex();
            string heroId;
            return instanceId != null && _equippedByInstance.TryGetValue(instanceId, out heroId) ? heroId : null;
        }

        /// <summary>Instance currently occupying (heroId, slot), or null.</summary>
        public string GetEquipped(string heroId, EquipmentSlot slot)
        {
            EnsureIndex();
            HeroLoadout loadout;
            if (!_byHero.TryGetValue(heroId ?? string.Empty, out loadout))
                return null;
            return loadout.SlotInstanceIds[SlotIndex(slot)];
        }

        /// <summary>
        /// Atomically equips an instance: validates inventory/definition/slot and
        /// the one-hero-per-instance rule, then swaps the slot in one step. Any
        /// previously equipped item stays in the inventory and simply becomes
        /// unequipped.
        /// </summary>
        public bool TryEquip(string heroId, string instanceId, EquipmentInventory inventory, EquipmentCatalog catalog)
        {
            if (string.IsNullOrWhiteSpace(heroId) || string.IsNullOrEmpty(instanceId))
                return false;
            if (inventory == null || catalog == null)
                return false;

            EnsureIndex();
            EquipmentInstance instance = inventory.Find(instanceId);
            if (instance == null)
                return false;

            EquipmentDefinition definition = catalog.Find(instance.DefinitionId);
            if (definition == null)
                return false;

            // Same instance cannot be equipped on two heroes; equipping on the
            // same hero into the matching slot is an idempotent no-op.
            string ownerHero;
            if (_equippedByInstance.TryGetValue(instanceId, out ownerHero))
            {
                if (!string.Equals(ownerHero, heroId, StringComparison.Ordinal))
                    return false;
                HeroLoadout own = _byHero[heroId];
                if (string.Equals(own.SlotInstanceIds[SlotIndex(definition.Slot)], instanceId, StringComparison.Ordinal))
                    return true;
                // Already equipped on this hero in a different slot cannot happen
                // because slot is fixed by the definition; reject defensively.
                return false;
            }

            int slotIdx = SlotIndex(definition.Slot);
            HeroLoadout loadout = GetOrCreateHero(heroId);

            // Atomic swap: set slot + index in one commit after all checks pass.
            string previous = loadout.SlotInstanceIds[slotIdx];
            loadout.SlotInstanceIds[slotIdx] = instanceId;
            _equippedByInstance[instanceId] = heroId;
            if (!string.IsNullOrEmpty(previous))
                _equippedByInstance.Remove(previous);
            return true;
        }

        /// <summary>Atomically clears a hero's slot; returns the unequipped instance ID or null.</summary>
        public string Unequip(string heroId, EquipmentSlot slot)
        {
            EnsureIndex();
            HeroLoadout loadout;
            if (!_byHero.TryGetValue(heroId ?? string.Empty, out loadout))
                return null;

            int slotIdx = SlotIndex(slot);
            string instanceId = loadout.SlotInstanceIds[slotIdx];
            if (string.IsNullOrEmpty(instanceId))
                return null;

            loadout.SlotInstanceIds[slotIdx] = null;
            _equippedByInstance.Remove(instanceId);
            return instanceId;
        }

        /// <summary>All equipped instance IDs for a hero (sorted by slot order, empties skipped).</summary>
        public List<string> EquippedInstances(string heroId)
        {
            EnsureIndex();
            var result = new List<string>();
            HeroLoadout loadout;
            if (_byHero.TryGetValue(heroId ?? string.Empty, out loadout))
            {
                for (int s = 0; s < loadout.SlotInstanceIds.Length; s++)
                    if (!string.IsNullOrEmpty(loadout.SlotInstanceIds[s]))
                        result.Add(loadout.SlotInstanceIds[s]);
            }
            return result;
        }
    }
}
