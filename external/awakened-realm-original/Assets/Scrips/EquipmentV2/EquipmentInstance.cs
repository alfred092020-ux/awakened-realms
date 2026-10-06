using System;

namespace AwakenedRealm.EquipmentV2
{
    [Serializable]
    public sealed class EquipmentInstance
    {
        public string InstanceId;
        public string DefinitionId;
        public int EnhancementLevel;
        public bool Locked;

        public EquipmentInstance() { }

        public EquipmentInstance(string instanceId, string definitionId)
        {
            if (string.IsNullOrWhiteSpace(instanceId))
                throw new ArgumentException("Instance ID is required.", nameof(instanceId));
            if (string.IsNullOrWhiteSpace(definitionId))
                throw new ArgumentException("Definition ID is required.", nameof(definitionId));

            InstanceId = instanceId;
            DefinitionId = definitionId;
            EnhancementLevel = 0;
            Locked = false;
        }
    }
}
