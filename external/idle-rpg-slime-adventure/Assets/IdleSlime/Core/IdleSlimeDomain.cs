using System;
using System.Collections.Generic;
using System.Linq;
namespace IdleSlime.Core {
public enum HeroRole{Guardian,Striker,Ranger,Mystic,Support} public enum HeroFaction{Ember,Tide,Verdant,Radiant,Umbral} public enum HeroRarity{Rare=3,Epic=4,Legendary=5,Mythic=6}
[Serializable] public sealed class HeroDefinition{public string Id,Name;public HeroRole Role;public HeroFaction Faction;public HeroRarity Rarity;public int BaseHp,BaseAttack,BaseDefense,Speed;public HeroDefinition(string id,string n,HeroRole r,HeroFaction f,HeroRarity q,int hp,int a,int d,int s){Id=id;Name=n;Role=r;Faction=f;Rarity=q;BaseHp=hp;BaseAttack=a;BaseDefense=d;Speed=s;}}
public static class HeroCatalog{public static readonly HeroDefinition[] All={
new HeroDefinition("cinder","Cinder",HeroRole.Striker,HeroFaction.Ember,HeroRarity.Legendary,760,128,54,108),new HeroDefinition("brasa","Brasa",HeroRole.Guardian,HeroFaction.Ember,HeroRarity.Epic,1120,76,96,72),new HeroDefinition("mistral","Mistral",HeroRole.Ranger,HeroFaction.Tide,HeroRarity.Legendary,720,121,58,116),new HeroDefinition("maris","Maris",HeroRole.Support,HeroFaction.Tide,HeroRarity.Epic,850,82,68,94),new HeroDefinition("briar","Briar",HeroRole.Guardian,HeroFaction.Verdant,HeroRarity.Legendary,1180,79,101,70),new HeroDefinition("fern","Fern",HeroRole.Mystic,HeroFaction.Verdant,HeroRarity.Epic,790,111,61,101),new HeroDefinition("solenne","Solenne",HeroRole.Mystic,HeroFaction.Radiant,HeroRarity.Legendary,810,124,62,104),new HeroDefinition("lux","Lux",HeroRole.Support,HeroFaction.Radiant,HeroRarity.Epic,900,78,72,96),new HeroDefinition("nyx","Nyx",HeroRole.Ranger,HeroFaction.Umbral,HeroRarity.Legendary,700,132,52,120),new HeroDefinition("vesper","Vesper",HeroRole.Striker,HeroFaction.Umbral,HeroRarity.Epic,770,118,56,112),new HeroDefinition("pippin","Pippin",HeroRole.Support,HeroFaction.Verdant,HeroRarity.Rare,820,70,65,90),new HeroDefinition("tavi","Tavi",HeroRole.Ranger,HeroFaction.Ember,HeroRarity.Rare,690,102,48,110)};public static HeroDefinition Get(string id){return All.FirstOrDefault(h=>h.Id==id);}}
[Serializable] public sealed class HeroState{public string HeroId;public int Level=1,Stars;public HeroState(string id){HeroId=id;var hero=HeroCatalog.Get(id);Stars=hero==null?1:StarRules.StartingStars(hero.Rarity);}[Obsolete("Use Stars. Ascension was replaced by star progression.")] public int Ascension{get{var h=HeroCatalog.Get(HeroId);return h==null?0:Math.Max(0,Stars-StarRules.StartingStars(h.Rarity));}set{var h=HeroCatalog.Get(HeroId);Stars=h==null?Math.Max(1,value):StarRules.ClampStars(h.Rarity,StarRules.StartingStars(h.Rarity)+Math.Max(0,value));}}public int VisualEvolutionStage{get{var hero=HeroCatalog.Get(HeroId);return hero==null?0:StarRules.VisualEvolutionStage(hero.Rarity,Stars);}}public string VisualAssetSuffix{get{var hero=HeroCatalog.Get(HeroId);return hero==null?"base":StarRules.VisualAssetSuffix(hero.Rarity,Stars);}}}
public sealed class Formation{public const int Size=5;public readonly string[] Slots;public Formation(IEnumerable<string> ids){Slots=ids.ToArray();if(Slots.Length!=5)throw new ArgumentException("Formation requires exactly five heroes.");if(Slots.Distinct().Count()!=5)throw new ArgumentException("Formation heroes must be unique.");if(Slots.Any(id=>HeroCatalog.Get(id)==null))throw new ArgumentException("Unknown hero.");}}
[Serializable] public sealed class CampaignStage{
 public int Number,EnemyPower,Gold,HeroXp,Gems;
 public bool Boss;
 public CampaignStage(int n,int p,int g,int x,int m,bool boss=false){Number=n;EnemyPower=p;Gold=g;HeroXp=x;Gems=m;Boss=boss;}
}
public static class CampaignCatalog{
 public const int MaxStage=50;
 public static readonly CampaignStage[] Stages=Enumerable.Range(1,MaxStage).Select(i=>{
  int chapter=(i-1)/10;
  int step=(i-1)%10;
  bool boss=i%10==0;
  int power=1450+(i-1)*350+chapter*250+step*20+(boss?200:0);
  int gold=120+i*42+chapter*85+(boss?600:0);
  int xp=45+i*14+chapter*25+(boss?120:0);
  int gems=boss?150:(i%5==0?60:15);
  return new CampaignStage(i,power,gold,xp,gems,boss);
 }).ToArray();
}
public sealed class BattleResult{public bool Victory;public int TeamPower,EnemyPower,Gold,HeroXp,Gems;} public static class BattleSimulator{public static int HeroPower(HeroState s){var h=HeroCatalog.Get(s.HeroId);if(h==null)throw new ArgumentException("Unknown hero.");double g=1+(s.Level-1)*.075+Math.Max(0,s.Stars-StarRules.StartingStars(h.Rarity))*.22;return (int)Math.Round((h.BaseHp*.36+h.BaseAttack*4.8+h.BaseDefense*3.2+h.Speed*1.4)*g);}public static BattleResult Resolve(Formation f,IReadOnlyDictionary<string,HeroState> r,CampaignStage s){int p=f.Slots.Sum(id=>HeroPower(r[id]));bool w=p>=s.EnemyPower;return new BattleResult{Victory=w,TeamPower=p,EnemyPower=s.EnemyPower,Gold=w?s.Gold:0,HeroXp=w?s.HeroXp:0,Gems=w?s.Gems:0};}}
public static class Progression{public static int GoldToLevel(int l){if(l<1)throw new ArgumentOutOfRangeException("l");return 60+l*45;}public static bool TryLevel(HeroState h,ref int gold){int c=GoldToLevel(h.Level);if(gold<c)return false;gold-=c;h.Level++;return true;}}
public interface IRandomSource{int Range(int min,int max);} public sealed class SeededRandom:IRandomSource{readonly Random r;public SeededRandom(int s){r=new Random(s);}public int Range(int a,int b){return r.Next(a,b);}} public static class Summoning{public const int SingleCost=300;public static HeroDefinition Roll(IRandomSource r){int x=r.Range(0,10000);HeroRarity q=x<300?HeroRarity.Legendary:x<2500?HeroRarity.Epic:HeroRarity.Rare;var p=HeroCatalog.All.Where(h=>h.Rarity==q).ToArray();return p[r.Range(0,p.Length)];}}
public struct IdleReward{public int Minutes,Gold,HeroXp;} public static class IdleRewards{public const int MaxMinutes=720;public static IdleReward Calculate(TimeSpan away,int highest){int m=Math.Max(0,Math.Min(MaxMinutes,(int)Math.Floor(away.TotalMinutes)));int s=Math.Max(1,Math.Min(CampaignCatalog.MaxStage,highest));return new IdleReward{Minutes=m,Gold=m*(4+s),HeroXp=m*(1+s/3)};}}
}
