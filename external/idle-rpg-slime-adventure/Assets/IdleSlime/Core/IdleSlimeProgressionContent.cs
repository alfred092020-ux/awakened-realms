using System;
using System.Collections.Generic;
using System.Linq;

namespace IdleSlime.Core {
public enum SkillKind { Basic, Active, Ultimate, Passive }
public enum EquipmentSlot { Weapon, Armor, Boots, Relic }
public enum QuestKind { Daily, Weekly, Progression }

[Serializable]
public sealed class SkillDefinition {
 public string Id, HeroId, Name, Description;
 public SkillKind Kind;
 public int UnlockAscension, PowerPercent, CooldownTurns;
 public SkillDefinition(string id,string heroId,string name,SkillKind kind,int unlock,int power,int cooldown,string description){
  Id=id;HeroId=heroId;Name=name;Kind=kind;UnlockAscension=unlock;PowerPercent=power;CooldownTurns=cooldown;Description=description;
 }
}

public static class SkillCatalog {
 static SkillDefinition S(string hero,string suffix,string name,SkillKind kind,int asc,int power,int cd,string desc){
  return new SkillDefinition(hero+"_"+suffix,hero,name,kind,asc,power,cd,desc);
 }
 public static readonly SkillDefinition[] All={
  S("cinder","basic","Ember Cut",SkillKind.Basic,0,100,0,"Single-target flame strike."),
  S("cinder","active","Blazing Arc",SkillKind.Active,0,145,3,"Sweeping attack with bonus damage."),
  S("cinder","ultimate","Phoenix Break",SkillKind.Ultimate,1,250,0,"Heavy burst against the enemy line."),
  S("cinder","passive","Heat Rising",SkillKind.Passive,2,18,0,"Attack increases as battle pressure rises."),
  S("brasa","basic","Shield Bash",SkillKind.Basic,0,90,0,"Guarding strike."),
  S("brasa","active","Molten Bulwark",SkillKind.Active,0,110,3,"Deals damage and reinforces the front line."),
  S("brasa","ultimate","Crater Guard",SkillKind.Ultimate,1,185,0,"Protective eruption that damages enemies."),
  S("brasa","passive","Iron Ember",SkillKind.Passive,2,20,0,"Defense bonus while deployed in front."),
  S("mistral","basic","Tide Arrow",SkillKind.Basic,0,105,0,"Fast ranged strike."),
  S("mistral","active","Riptide Volley",SkillKind.Active,0,155,3,"Multi-hit ranged attack."),
  S("mistral","ultimate","Horizon Spear",SkillKind.Ultimate,1,240,0,"Focused high-speed burst."),
  S("mistral","passive","Tailwind",SkillKind.Passive,2,14,0,"Speed bonus to the formation."),
  S("maris","basic","Foam Bolt",SkillKind.Basic,0,85,0,"Supportive ranged attack."),
  S("maris","active","Restoring Current",SkillKind.Active,0,80,3,"Restores team vitality while dealing light damage."),
  S("maris","ultimate","Moonlit Tide",SkillKind.Ultimate,1,150,0,"Team recovery and enemy pressure."),
  S("maris","passive","Calm Waters",SkillKind.Passive,2,16,0,"Improves recovery effects."),
  S("briar","basic","Thorn Slam",SkillKind.Basic,0,92,0,"Heavy guardian strike."),
  S("briar","active","Rootwall",SkillKind.Active,0,120,3,"Damages and fortifies allies."),
  S("briar","ultimate","Ancient Grove",SkillKind.Ultimate,1,190,0,"Massive defensive counterattack."),
  S("briar","passive","Deep Roots",SkillKind.Passive,2,22,0,"Maximum health bonus."),
  S("fern","basic","Spore Lance",SkillKind.Basic,0,102,0,"Mystic nature bolt."),
  S("fern","active","Bloom Hex",SkillKind.Active,0,150,3,"Mystic burst with weakening spores."),
  S("fern","ultimate","Verdant Nova",SkillKind.Ultimate,1,225,0,"Area burst of verdant energy."),
  S("fern","passive","Wild Insight",SkillKind.Passive,2,15,0,"Improves skill damage."),
  S("solenne","basic","Ray",SkillKind.Basic,0,104,0,"Radiant magic strike."),
  S("solenne","active","Prism Fall",SkillKind.Active,0,158,3,"Radiant area attack."),
  S("solenne","ultimate","Solar Crown",SkillKind.Ultimate,1,245,0,"High-output radiant burst."),
  S("solenne","passive","Dawn Oath",SkillKind.Passive,2,15,0,"Raises formation attack."),
  S("lux","basic","Gleam",SkillKind.Basic,0,82,0,"Support magic strike."),
  S("lux","active","Beacon",SkillKind.Active,0,95,3,"Bolsters allies and damages enemies."),
  S("lux","ultimate","Sanctuary Pulse",SkillKind.Ultimate,1,160,0,"Formation-wide sustain burst."),
  S("lux","passive","Guiding Light",SkillKind.Passive,2,15,0,"Raises formation defense."),
  S("nyx","basic","Nightshot",SkillKind.Basic,0,108,0,"Fast umbral shot."),
  S("nyx","active","Shadow Barrage",SkillKind.Active,0,165,3,"Rapid multi-hit attack."),
  S("nyx","ultimate","Black Comet",SkillKind.Ultimate,1,255,0,"Extreme single-target burst."),
  S("nyx","passive","Predator",SkillKind.Passive,2,18,0,"Bonus damage against weakened foes."),
  S("vesper","basic","Dusk Edge",SkillKind.Basic,0,103,0,"Umbral melee strike."),
  S("vesper","active","Nightfall",SkillKind.Active,0,152,3,"Dark area slash."),
  S("vesper","ultimate","Eclipse Dance",SkillKind.Ultimate,1,235,0,"Repeated high-speed strikes."),
  S("vesper","passive","Afterimage",SkillKind.Passive,2,14,0,"Speed and evasion flavor bonus."),
  S("pippin","basic","Seed Pop",SkillKind.Basic,0,78,0,"Small support strike."),
  S("pippin","active","Lucky Sprout",SkillKind.Active,0,90,3,"Supports allies with a restorative burst."),
  S("pippin","ultimate","Festival Bloom",SkillKind.Ultimate,1,145,0,"Large support burst."),
  S("pippin","passive","Good Fortune",SkillKind.Passive,2,12,0,"Improves reward-side support flavor."),
  S("tavi","basic","Spark Shot",SkillKind.Basic,0,101,0,"Quick ember projectile."),
  S("tavi","active","Flash Volley",SkillKind.Active,0,148,3,"Fast ranged burst."),
  S("tavi","ultimate","Redline Salvo",SkillKind.Ultimate,1,220,0,"High-speed ember barrage."),
  S("tavi","passive","Hot Start",SkillKind.Passive,2,12,0,"Starts battle with bonus energy.")
 };
 public static IEnumerable<SkillDefinition> ForHero(string heroId){return All.Where(s=>s.HeroId==heroId);}
}

[Serializable]
public sealed class EquipmentDefinition {
 public string Id,Name,SetId;
 public EquipmentSlot Slot;
 public HeroRarity Rarity;
 public int Power;
 public EquipmentDefinition(string id,string name,string set,EquipmentSlot slot,HeroRarity rarity,int power){
  Id=id;Name=name;SetId=set;Slot=slot;Rarity=rarity;Power=power;
 }
}

public static class EquipmentCatalog {
 public static readonly EquipmentDefinition[] All={
  new EquipmentDefinition("ember_blade","Emberglass Blade","emberguard",EquipmentSlot.Weapon,HeroRarity.Epic,180),
  new EquipmentDefinition("ember_plate","Emberguard Plate","emberguard",EquipmentSlot.Armor,HeroRarity.Epic,165),
  new EquipmentDefinition("ember_steps","Emberguard Steps","emberguard",EquipmentSlot.Boots,HeroRarity.Epic,145),
  new EquipmentDefinition("ember_core","Ember Core","emberguard",EquipmentSlot.Relic,HeroRarity.Legendary,240),
  new EquipmentDefinition("tide_bow","Tidecaller Bow","tidecaller",EquipmentSlot.Weapon,HeroRarity.Epic,180),
  new EquipmentDefinition("tide_mail","Tidecaller Mail","tidecaller",EquipmentSlot.Armor,HeroRarity.Epic,165),
  new EquipmentDefinition("tide_stride","Tidecaller Stride","tidecaller",EquipmentSlot.Boots,HeroRarity.Epic,145),
  new EquipmentDefinition("tide_pearl","Abyssal Pearl","tidecaller",EquipmentSlot.Relic,HeroRarity.Legendary,240),
  new EquipmentDefinition("verdant_staff","Verdant Staff","evergreen",EquipmentSlot.Weapon,HeroRarity.Epic,180),
  new EquipmentDefinition("verdant_hide","Evergreen Hide","evergreen",EquipmentSlot.Armor,HeroRarity.Epic,165),
  new EquipmentDefinition("verdant_roots","Evergreen Roots","evergreen",EquipmentSlot.Boots,HeroRarity.Epic,145),
  new EquipmentDefinition("verdant_seed","Worldseed","evergreen",EquipmentSlot.Relic,HeroRarity.Legendary,240),
  new EquipmentDefinition("radiant_scepter","Radiant Scepter","dawn",EquipmentSlot.Weapon,HeroRarity.Epic,180),
  new EquipmentDefinition("radiant_robe","Dawn Robe","dawn",EquipmentSlot.Armor,HeroRarity.Epic,165),
  new EquipmentDefinition("radiant_wings","Dawn Wings","dawn",EquipmentSlot.Boots,HeroRarity.Epic,145),
  new EquipmentDefinition("radiant_halo","Sun Halo","dawn",EquipmentSlot.Relic,HeroRarity.Legendary,240),
  new EquipmentDefinition("umbral_dagger","Umbral Dagger","eclipse",EquipmentSlot.Weapon,HeroRarity.Epic,180),
  new EquipmentDefinition("umbral_coat","Eclipse Coat","eclipse",EquipmentSlot.Armor,HeroRarity.Epic,165),
  new EquipmentDefinition("umbral_step","Eclipse Step","eclipse",EquipmentSlot.Boots,HeroRarity.Epic,145),
  new EquipmentDefinition("umbral_eye","Void Eye","eclipse",EquipmentSlot.Relic,HeroRarity.Legendary,240)
 };
 public static EquipmentDefinition Get(string id){return All.FirstOrDefault(x=>x.Id==id);}
}

public static class AscensionRules {
 public const int MaxAscension=5;
 public static int GoldCost(int ascension){if(ascension<0||ascension>=MaxAscension)throw new ArgumentOutOfRangeException("ascension");return 800+(ascension*650);}
 public static int ShardCost(int ascension){if(ascension<0||ascension>=MaxAscension)throw new ArgumentOutOfRangeException("ascension");return 20+(ascension*15);}
}

[Serializable]
public sealed class RewardBundle {
 public int Gold,Gems,HeroXp,AscensionShards;
 public string EquipmentId;
 public RewardBundle(){}
 public RewardBundle(int gold,int gems,int xp,int shards,string equipmentId=null){Gold=gold;Gems=gems;HeroXp=xp;AscensionShards=shards;EquipmentId=equipmentId;}
}

[Serializable]
public sealed class QuestDefinition {
 public string Id,Title,Metric;
 public QuestKind Kind;
 public int Target;
 public RewardBundle Reward;
 public QuestDefinition(string id,string title,QuestKind kind,string metric,int target,RewardBundle reward){Id=id;Title=title;Kind=kind;Metric=metric;Target=target;Reward=reward;}
}

public static class QuestCatalog {
 public static readonly QuestDefinition[] All={
  new QuestDefinition("d_battle_3","Win 3 Campaign Battles",QuestKind.Daily,"campaign_wins",3,new RewardBundle(300,25,0,2)),
  new QuestDefinition("d_level_2","Level Heroes 2 Times",QuestKind.Daily,"hero_levels",2,new RewardBundle(250,20,0,2)),
  new QuestDefinition("d_summon_1","Summon 1 Hero",QuestKind.Daily,"summons",1,new RewardBundle(200,30,0,1)),
  new QuestDefinition("d_idle_1","Claim Idle Rewards",QuestKind.Daily,"idle_claims",1,new RewardBundle(220,20,0,2)),
  new QuestDefinition("w_battle_20","Win 20 Campaign Battles",QuestKind.Weekly,"campaign_wins",20,new RewardBundle(1800,180,0,12)),
  new QuestDefinition("w_summon_10","Summon 10 Heroes",QuestKind.Weekly,"summons",10,new RewardBundle(1200,220,0,10)),
  new QuestDefinition("w_tower_10","Clear 10 Tower Floors",QuestKind.Weekly,"tower_clears",10,new RewardBundle(1500,200,0,15)),
  new QuestDefinition("p_stage_10","Reach Campaign Stage 10",QuestKind.Progression,"highest_stage",10,new RewardBundle(1000,120,0,8)),
  new QuestDefinition("p_stage_25","Reach Campaign Stage 25",QuestKind.Progression,"highest_stage",25,new RewardBundle(2500,250,0,18)),
  new QuestDefinition("p_stage_50","Reach Campaign Stage 50",QuestKind.Progression,"highest_stage",50,new RewardBundle(6000,600,0,40))
 };
 public static QuestDefinition Get(string id){return All.FirstOrDefault(q=>q.Id==id);}
}

[Serializable]
public sealed class DailyRewardDefinition {
 public int Day;
 public RewardBundle Reward;
 public DailyRewardDefinition(int day,RewardBundle reward){Day=day;Reward=reward;}
}
public static class DailyRewardCatalog {
 public static readonly DailyRewardDefinition[] Cycle={
  new DailyRewardDefinition(1,new RewardBundle(500,50,0,3)),
  new DailyRewardDefinition(2,new RewardBundle(650,60,0,4)),
  new DailyRewardDefinition(3,new RewardBundle(800,70,0,5)),
  new DailyRewardDefinition(4,new RewardBundle(1000,80,0,6)),
  new DailyRewardDefinition(5,new RewardBundle(1250,100,0,8)),
  new DailyRewardDefinition(6,new RewardBundle(1500,120,0,10)),
  new DailyRewardDefinition(7,new RewardBundle(2500,300,0,20,"radiant_halo"))
 };
}

[Serializable]
public sealed class AchievementDefinition {
 public string Id,Title,Metric;
 public int Target;
 public RewardBundle Reward;
 public AchievementDefinition(string id,string title,string metric,int target,RewardBundle reward){Id=id;Title=title;Metric=metric;Target=target;Reward=reward;}
}
public static class AchievementCatalog {
 public static readonly AchievementDefinition[] All={
  new AchievementDefinition("roster_8","Growing Roster","heroes_owned",8,new RewardBundle(500,100,0,5)),
  new AchievementDefinition("roster_12","Realm Collector","heroes_owned",12,new RewardBundle(1200,250,0,12)),
  new AchievementDefinition("stage_20","Frontier Breaker","highest_stage",20,new RewardBundle(1800,180,0,12)),
  new AchievementDefinition("stage_50","Realm Awakened","highest_stage",50,new RewardBundle(5000,500,0,30)),
  new AchievementDefinition("ascend_5","First Ascendant","total_ascensions",5,new RewardBundle(2000,200,0,15)),
  new AchievementDefinition("tower_30","Tower Conqueror","tower_clears",30,new RewardBundle(3500,350,0,25))
 };
}

[Serializable]
public sealed class TowerFloorDefinition {
 public int Floor,EnemyPower;
 public RewardBundle Reward;
 public TowerFloorDefinition(int floor,int power,RewardBundle reward){Floor=floor;EnemyPower=power;Reward=reward;}
}
public static class TowerCatalog {
 public static readonly TowerFloorDefinition[] Floors=Enumerable.Range(1,30)
  .Select(i=>new TowerFloorDefinition(i,2100+(i-1)*430+(i/5)*240,new RewardBundle(250+i*45,i%5==0?75:20,0,i%5==0?5:1)))
  .ToArray();
}

[Serializable]
public sealed class BossDefinition {
 public string Id,Name;
 public HeroFaction Faction;
 public int RecommendedPower;
 public RewardBundle Reward;
 public BossDefinition(string id,string name,HeroFaction faction,int power,RewardBundle reward){Id=id;Name=name;Faction=faction;RecommendedPower=power;Reward=reward;}
}
public static class BossCatalog {
 public static readonly BossDefinition[] All={
  new BossDefinition("pyre_tyrant","Pyre Tyrant",HeroFaction.Ember,6500,new RewardBundle(1800,80,0,8)),
  new BossDefinition("leviathan","Abyss Leviathan",HeroFaction.Tide,10500,new RewardBundle(2600,100,0,10)),
  new BossDefinition("worldroot","Worldroot Colossus",HeroFaction.Verdant,15500,new RewardBundle(3400,120,0,12)),
  new BossDefinition("seraph","Fallen Seraph",HeroFaction.Radiant,22000,new RewardBundle(4500,150,0,15)),
  new BossDefinition("null_queen","Null Queen",HeroFaction.Umbral,30000,new RewardBundle(6000,200,0,20))
 };
 public static BossDefinition Get(string id){return All.FirstOrDefault(b=>b.Id==id);}
}

[Serializable]
public sealed class MailEnvelope {
 public string Id,Subject,Body;
 public RewardBundle Reward;
 public MailEnvelope(string id,string subject,string body,RewardBundle reward){Id=id;Subject=subject;Body=body;Reward=reward;}
}

public static class LaunchMailCatalog {
 public static readonly MailEnvelope[] All={
  new MailEnvelope("launch_welcome","Welcome, Awakened","Thank you for joining the first expedition.",new RewardBundle(1500,600,0,15)),
  new MailEnvelope("launch_supply","Launch Supply Cache","A supply cache from Nexus Core.",new RewardBundle(2500,300,0,10,"ember_blade"))
 };
}
}
