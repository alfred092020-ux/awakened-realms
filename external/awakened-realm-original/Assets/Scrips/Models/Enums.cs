namespace AwakenedRealm.Enums
{



    public enum MainMenuButtonType
    {
        settings, formation, battle, towm, hero, normal
    }

    public enum HeroCategory { attack, tank, projectile }
    public enum HeroRank { bronze, gold, topTier }
    public enum HeroRarity { common, rare, epic, legendary, mythic }

    public enum Dragging { started, released }
    public enum HeroAnimationState { Idle, Walk, Attack }
    public enum Teams { hero, enemy, NULL }
    public enum TicketType { basic, advance }
    public enum CharacterType { hero, enemy, boss }
}