using System;
using System.Collections.Generic;

namespace AwakenedRealm.EquipmentV2
{
    /// <summary>
    /// Player inventory of equipment instances plus the shared wallet used by
    /// enhancement. Enforces unique instance IDs and known definition IDs.
    /// </summary>
    [Serializable]
    public sealed class EquipmentInventory
    {
        public List<EquipmentInstance> Items = new List<EquipmentInstance>();
        public EquipmentWallet Wallet = new EquipmentWallet();

        // Runtime index rebuilt after deserialization; not persisted directly.
        Dictionary<string, EquipmentInstance> _byId;

        void EnsureIndex()
        {
            if (_byId == null)
            {
                _byId = new Dictionary<string, EquipmentInstance>(StringComparer.Ordinal);
                for (int i = 0; i < Items.Count; i++)
                {
                    EquipmentInstance item = Items[i];
                    if (item == null || string.IsNullOrWhiteSpace(item.InstanceId))
                        throw new InvalidOperationException("Inventory contains an item without a valid instance ID.");
                    if (_byId.ContainsKey(item.InstanceId))
                        throw new InvalidOperationException("Duplicate instance ID in inventory: " + item.InstanceId);
                    _byId[item.InstanceId] = item;
                }
            }
        }

        public bool Contains(string instanceId)
        {
            EnsureIndex();
            return instanceId != null && _byId.ContainsKey(instanceId);
        }

        public EquipmentInstance Find(string instanceId)
        {
            EnsureIndex();
            EquipmentInstance item;
            return _byId.TryGetValue(instanceId ?? string.Empty, out item) ? item : null;
        }

        public int Count
        {
            get { return Items.Count; }
        }

        /// <summary>Adds an instance; rejects duplicates and unknown definitions.</summary>
        public bool TryAdd(EquipmentInstance instance, EquipmentCatalog catalog)
        {
            if (instance == null || catalog == null)
                return false;
            EnsureIndex();
            if (string.IsNullOrWhiteSpace(instance.InstanceId) || _byId.ContainsKey(instance.InstanceId))
                return false;
            if (catalog.Find(instance.DefinitionId) == null)
                return false;

            _byId[instance.InstanceId] = instance;
            Items.Add(instance);
            return true;
        }

        public bool SetLocked(string instanceId, bool locked)
        {
            EquipmentInstance item = Find(instanceId);
            if (item == null)
                return false;
            item.Locked = locked;
            return true;
        }

        /// <summary>Removes an item only when it is neither locked nor equipped.</summary>
        public bool TryRemove(string instanceId, EquipmentLoadouts loadouts)
        {
            EnsureIndex();
            EquipmentInstance item = Find(instanceId);
            if (item == null || item.Locked)
                return false;
            if (loadouts != null && loadouts.IsEquipped(instanceId))
                return false;

            _byId.Remove(instanceId);
            Items.Remove(item);
            return true;
        }
    }
}
