#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using AwakenedRealm.EquipmentV2;
using UnityEditor;
using UnityEngine;

public static class ValidateEquipmentV2
{
    [MenuItem("Awakened Realms/Validate Equipment V2")]
    public static void Run()
    {
        EquipmentCatalog catalog = EquipmentCatalog.CreateDefault();

        // All default catalog entries validate; covers every slot x rarity.
        catalog.ValidateAll();
        foreach (EquipmentSlot slot in Enum.GetValues(typeof(EquipmentSlot)))
            foreach (EquipmentRarity rarity in Enum.GetValues(typeof(EquipmentRarity)))
                Assert(HasEntry(catalog, slot, rarity), "Default catalog covers " + rarity + " " + slot);

        // Duplicate definition IDs rejected.
        var dupCatalog = new EquipmentCatalog();
        dupCatalog.Add(new EquipmentDefinition("eq_dup", "A", EquipmentSlot.Weapon, EquipmentRarity.Rare, 1, null,
            StatModifier.FlatOf(EquipmentStatType.ATK, 10f)));
        Assert(!dupCatalog.TryAdd(new EquipmentDefinition("eq_dup", "B", EquipmentSlot.Weapon, EquipmentRarity.Rare, 1, null,
            StatModifier.FlatOf(EquipmentStatType.ATK, 20f))), "Duplicate definition ID rejected");

        // Rarity caps.
        Assert(EnhancementRules.MaxEnhancement(EquipmentRarity.Rare) == 10, "Rare cap +10");
        Assert(EnhancementRules.MaxEnhancement(EquipmentRarity.Epic) == 15, "Epic cap +15");
        Assert(EnhancementRules.MaxEnhancement(EquipmentRarity.Legendary) == 20, "Legendary cap +20");
        Assert(EnhancementRules.MaxEnhancement(EquipmentRarity.Mythic) == 25, "Mythic cap +25");

        // Enhancement costs strictly monotonic per rarity.
        foreach (EquipmentRarity rarity in Enum.GetValues(typeof(EquipmentRarity)))
        {
            long prevGold = -1;
            int prevStones = -1;
            for (int lvl = 1; lvl <= EnhancementRules.MaxEnhancement(rarity); lvl++)
            {
                long gold;
                int stones;
                EnhancementRules.CostForLevel(rarity, lvl, out gold, out stones);
                Assert(gold > prevGold && stones > prevStones, "Cost monotonic for " + rarity + " level " + lvl);
                prevGold = gold;
                prevStones = stones;
            }
        }

        // Atomic insufficient-resource behavior: wallet untouched, level unchanged.
        EquipmentDefinition sword = catalog.Find("eq_r_wpn_dawnsword");
        var instance = new EquipmentInstance("inst-1", sword.DefinitionId);
        var wallet = new EquipmentWallet(0, 0);
        Assert(!EnhancementRules.TryEnhance(instance, sword, wallet), "Enhance rejects empty wallet");
        Assert(instance.EnhancementLevel == 0 && wallet.Gold == 0 && wallet.EnhancementStones == 0,
            "Failed enhance is atomic");

        // Successful enhance consumes exact cost and raises level by one.
        long needGold;
        int needStones;
        EnhancementRules.CostForLevel(sword.Rarity, 1, out needGold, out needStones);
        wallet = new EquipmentWallet(needGold, needStones);
        Assert(EnhancementRules.TryEnhance(instance, sword, wallet), "Enhance succeeds with exact resources");
        Assert(instance.EnhancementLevel == 1 && wallet.Gold == 0 && wallet.EnhancementStones == 0,
            "Exact resources consumed");

        // Cap enforced at max.
        var capped = new EquipmentInstance("inst-cap", sword.DefinitionId) { EnhancementLevel = 10 };
        var rich = new EquipmentWallet(999999999L, 999999);
        Assert(!EnhancementRules.TryEnhance(capped, sword, rich), "Enhance rejected at cap");

        // Inventory: unique instance IDs and known definitions.
        var inventory = new EquipmentInventory();
        var loadouts = new EquipmentLoadouts();
        Assert(inventory.TryAdd(instance, catalog), "Inventory accepts valid instance");
        Assert(!inventory.TryAdd(new EquipmentInstance("inst-1", sword.DefinitionId), catalog),
            "Duplicate instance ID rejected");
        Assert(!inventory.TryAdd(new EquipmentInstance("inst-2", "eq_unknown"), catalog),
            "Unknown definition rejected");

        // Slot correctness: a helmet occupies only the helmet slot.
        EquipmentDefinition helm = catalog.Find("eq_r_hlm_wardenhelm");
        var helmet = new EquipmentInstance("inst-helm", helm.DefinitionId);
        Assert(inventory.TryAdd(helmet, catalog), "Helmet added");
        Assert(loadouts.TryEquip("hero-a", "inst-helm", inventory, catalog), "Helmet equips into helmet slot");
        Assert(string.Equals(loadouts.GetEquipped("hero-a", EquipmentSlot.Helmet), "inst-helm"), "Helmet occupies helmet slot");
        Assert(loadouts.GetEquipped("hero-a", EquipmentSlot.Weapon) == null, "Weapon slot unaffected by helmet");

        // Same instance cannot equip on two heroes.
        Assert(loadouts.TryEquip("hero-a", "inst-1", inventory, catalog), "Equip hero-a sword");
        Assert(!loadouts.TryEquip("hero-b", "inst-1", inventory, catalog), "Same instance cannot equip on second hero");

        // Equip swap is atomic and frees the replaced instance.
        var sword2 = new EquipmentInstance("inst-3", sword.DefinitionId);
        Assert(inventory.TryAdd(sword2, catalog), "Second sword added");
        Assert(loadouts.TryEquip("hero-a", "inst-3", inventory, catalog), "Swap to second sword");
        Assert(string.Equals(loadouts.GetEquipped("hero-a", EquipmentSlot.Weapon), "inst-3"), "Slot now holds second sword");
        Assert(!loadouts.IsEquipped("inst-1"), "Replaced sword no longer equipped");

        // Unequip is deterministic and frees the instance.
        Assert(string.Equals(loadouts.Unequip("hero-a", EquipmentSlot.Weapon), "inst-3"), "Unequip returns instance");
        Assert(loadouts.GetEquipped("hero-a", EquipmentSlot.Weapon) == null, "Slot cleared after unequip");

        // Set bonuses: 2pc then 4pc activation from equipped pieces.
        var setInventory = new EquipmentInventory();
        var setLoadouts = new EquipmentLoadouts();
        string[] setPieces = { "eq_m_wpn_starfang", "eq_l_hlm_dawncrown", "eq_r_arm_dawnplate", "eq_l_bts_dawngreaves" };
        for (int i = 0; i < setPieces.Length; i++)
        {
            string iid = "set-piece-" + i;
            Assert(setInventory.TryAdd(new EquipmentInstance(iid, setPieces[i]), catalog), "Set piece added " + iid);
            Assert(setLoadouts.TryEquip("hero-set", iid, setInventory, catalog), "Set piece equipped " + iid);
        }
        List<StatModifier> mods = EquipmentSetBonuses.AggregateActiveModifiers("hero-set", setLoadouts, setInventory, catalog);
        float atkPct = SumPercent(mods, EquipmentStatType.ATK);
        float critPct = SumPercent(mods, EquipmentStatType.CritRate);
        Assert(Mathf.Approximately(atkPct, 0.24f), "Dawnbreak 2pc+4pc ATK% aggregates (0.08+0.16)");
        Assert(Mathf.Approximately(critPct, 0.10f), "Dawnbreak 4pc CritRate applies");

        // 2-piece-only activation: strip down to 2 pieces.
        setLoadouts.Unequip("hero-set", EquipmentSlot.Helmet);
        setLoadouts.Unequip("hero-set", EquipmentSlot.Boots);
        mods = EquipmentSetBonuses.AggregateActiveModifiers("hero-set", setLoadouts, setInventory, catalog);
        atkPct = SumPercent(mods, EquipmentStatType.ATK);
        critPct = SumPercent(mods, EquipmentStatType.CritRate);
        Assert(Mathf.Approximately(atkPct, 0.08f), "2pc only gives 0.08 ATK%");
        Assert(Mathf.Approximately(critPct, 0f), "4pc bonus inactive at 2 pieces");

        // Locked and equipped items cannot be removed.
        Assert(loadouts.TryEquip("hero-a", "inst-3", inventory, catalog), "Re-equip for removal test");
        Assert(!inventory.TryRemove("inst-3", loadouts), "Equipped item cannot be removed");
        Assert(loadouts.Unequip("hero-a", EquipmentSlot.Weapon) != null, "Sword unequipped");
        Assert(inventory.SetLocked("inst-3", true), "Lock applied");
        Assert(!inventory.TryRemove("inst-3", loadouts), "Locked item cannot be removed");
        Assert(inventory.SetLocked("inst-3", false), "Unlock applied");
        Assert(inventory.TryRemove("inst-3", loadouts), "Unlocked unequipped item removable");

        // Deterministic power score.
        var pInstance = new EquipmentInstance("pow-1", "eq_l_wpn_arcanestaff") { EnhancementLevel = 10 };
        float p1 = EquipmentPower.InstancePower(pInstance, catalog.Find("eq_l_wpn_arcanestaff"));
        float p2 = EquipmentPower.InstancePower(pInstance, catalog.Find("eq_l_wpn_arcanestaff"));
        Assert(Mathf.Approximately(p1, p2), "Power score deterministic");
        var pBase = new EquipmentInstance("pow-2", "eq_l_wpn_arcanestaff");
        Assert(p1 > EquipmentPower.InstancePower(pBase, catalog.Find("eq_l_wpn_arcanestaff")),
            "Enhancement raises power score");

        Debug.Log("AWAKENED_REALMS_EQUIPMENT_V2_PASS");
    }

    static bool HasEntry(EquipmentCatalog catalog, EquipmentSlot slot, EquipmentRarity rarity)
    {
        for (int i = 0; i < catalog.Definitions.Count; i++)
            if (catalog.Definitions[i].Slot == slot && catalog.Definitions[i].Rarity == rarity)
                return true;
        return false;
    }

    static float SumPercent(List<StatModifier> mods, EquipmentStatType stat)
    {
        float total = 0f;
        for (int i = 0; i < mods.Count; i++)
            if (mods[i].Stat == stat)
                total += mods[i].Percent;
        return total;
    }

    static void Assert(bool condition, string label)
    {
        if (!condition)
            throw new InvalidOperationException("Equipment V2 validation failed: " + label);
    }
}
#endif
