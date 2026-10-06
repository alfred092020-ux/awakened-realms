namespace AwakenedRealm.CombatV2
{
    /// <summary>
    /// High-level combat role for a hero kit. Drives formation preference
    /// and explicit protection targeting rules.
    /// </summary>
    public enum HeroRole
    {
        Dps,
        Support,
        Defender
    }

    /// <summary>
    /// Primary scaling stat used by a hero's damage or healing.
    /// </summary>
    public enum ScalingStat
    {
        Attack,
        Magic,
        MaxHealth,
        Defense
    }

    /// <summary>
    /// Physical range style of a hero. Affects how positional rules
    /// (front/back row modifiers) are interpreted.
    /// </summary>
    public enum RangeStyle
    {
        Melee,
        Long
    }

    /// <summary>
    /// The four ability slots every hero kit exposes.
    /// </summary>
    public enum AbilitySlot
    {
        Basic,
        Skill,
        Passive,
        Ultimate
    }

    /// <summary>
    /// Deterministic targeting pattern resolved against the stable 3x3 grid.
    /// </summary>
    public enum TargetPattern
    {
        None,
        Self,
        SingleEnemy,
        SingleAlly,
        RowEnemies,
        ColumnEnemies,
        AdjacentEnemies,
        AllEnemies,
        AllAllies,
        LowestHealthEnemy,
        LowestHealthAlly
    }

    /// <summary>
    /// High-level effect a status or buff applies to a combat unit.
    /// </summary>
    public enum EffectType
    {
        StatModifier,
        DamageOverTime,
        HealOverTime,
        Shield,
        CrowdControl,
        Utility
    }

    /// <summary>
    /// Canon status and buff types. Root and Bleed are declared for
    /// extensibility; their numeric behavior is intentionally unspecified.
    /// </summary>
    public enum StatusType
    {
        None,
        AttackUp,
        DefenseUp,
        MagicUp,
        SpeedUp,
        CritUp,
        ResistanceUp,
        HealOverTime,
        Shield,
        EnergyCharge,
        AttackDown,
        DefenseDown,
        MagicDown,
        SpeedDown,
        CritDown,
        ResistanceDown,
        Burn,
        Poison,
        Stun,
        Silence,
        Blind,
        Root,
        Bleed,
        Taunt
    }
}
