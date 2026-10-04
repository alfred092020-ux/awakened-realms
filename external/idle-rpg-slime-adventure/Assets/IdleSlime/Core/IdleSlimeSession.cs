using System;
using System.Collections.Generic;
using System.Linq;

namespace IdleSlime.Core {
public sealed class IdleSlimeSession {
 public readonly Dictionary<string,HeroState> Heroes=new Dictionary<string,HeroState>();
 public readonly Dictionary<string,int> EquipmentInventory=new Dictionary<string,int>();
 public readonly Dictionary<string,string> EquippedItems=new Dictionary<string,string>();
 public readonly HashSet<string> ClaimedQuestIds=new HashSet<string>();
 public readonly HashSet<string> ClaimedAchievementIds=new HashSet<string>();
 public readonly HashSet<string> ClaimedMailIds=new HashSet<string>();
 public readonly HashSet<string> ClaimedBossIds=new HashSet<string>();
 public readonly Dictionary<string,int> Metrics=new Dictionary<string,int>();

 public Formation Formation{get;private set;}
 public int Gold{get;private set;}
 public int Gems{get;private set;}
 public int AscensionShards{get;private set;}
 public int HighestStage{get;private set;}=1;
 public int HighestTowerFloor{get;private set;}=1;
 public int DailyRewardDay{get;private set;}=1;
 public DateTime LastSeenUtc{get;private set;}
 public DateTime LastDailyClaimUtc{get;private set;}=DateTime.MinValue;

 public IdleSlimeSession(DateTime now){
  LastSeenUtc=now;
  foreach(var h in HeroCatalog.All.Take(5))Heroes[h.Id]=new HeroState(h.Id);
  Formation=new Formation(Heroes.Keys.Take(5));
  Gold=500;
  Gems=600;
 }

 public IdleReward ClaimIdle(DateTime now){
  var r=IdleRewards.Calculate(now-LastSeenUtc,HighestStage);
  Gold+=r.Gold;
  LastSeenUtc=now;
  IncrementMetric("idle_claims");
  return r;
 }

 public BattleResult Fight(){
  var stage=CampaignCatalog.Stages[Math.Max(0,Math.Min(CampaignCatalog.MaxStage-1,HighestStage-1))];
  var result=BattleSimulator.Resolve(Formation,Heroes,stage);
  if(result.Victory){
   Gold+=result.Gold;
   Gems+=result.Gems;
   IncrementMetric("campaign_wins");
   if(HighestStage<CampaignCatalog.MaxStage)HighestStage++;
  }
  return result;
 }

 public bool Upgrade(string id){
  HeroState hero;
  if(!Heroes.TryGetValue(id,out hero))return false;
  int gold=Gold;
  if(!Progression.TryLevel(hero,ref gold))return false;
  Gold=gold;
  IncrementMetric("hero_levels");
  return true;
 }

 public bool TryAscend(string id){
  HeroState hero;
  if(!Heroes.TryGetValue(id,out hero))return false;
  if(hero.Ascension>=AscensionRules.MaxAscension)return false;
  int levelGate=10+(hero.Ascension*10);
  if(hero.Level<levelGate)return false;
  int gold=AscensionRules.GoldCost(hero.Ascension);
  int shards=AscensionRules.ShardCost(hero.Ascension);
  if(Gold<gold||AscensionShards<shards)return false;
  Gold-=gold;
  AscensionShards-=shards;
  hero.Ascension++;
  IncrementMetric("total_ascensions");
  return true;
 }

 public HeroDefinition Summon(IRandomSource rng){
  if(Gems<Summoning.SingleCost)return null;
  Gems-=Summoning.SingleCost;
  var hero=Summoning.Roll(rng);
  if(!Heroes.ContainsKey(hero.Id)){
   Heroes[hero.Id]=new HeroState(hero.Id);
  }else{
   AscensionShards+=DuplicateShardValue(hero.Rarity);
  }
  IncrementMetric("summons");
  return hero;
 }

 public void SetFormation(IEnumerable<string> ids){
  foreach(var id in ids)if(!Heroes.ContainsKey(id))throw new ArgumentException("Hero not owned: "+id);
  Formation=new Formation(ids);
 }

 public bool Equip(string heroId,string equipmentId){
  if(!Heroes.ContainsKey(heroId))return false;
  var item=EquipmentCatalog.Get(equipmentId);
  if(item==null)return false;
  int count;
  if(!EquipmentInventory.TryGetValue(equipmentId,out count)||count<=0)return false;
  string key=EquipmentKey(heroId,item.Slot);
  string previous;
  if(EquippedItems.TryGetValue(key,out previous)){
   if(previous==equipmentId)return true;
   AddEquipment(previous,1);
  }
  EquipmentInventory[equipmentId]=count-1;
  EquippedItems[key]=equipmentId;
  return true;
 }

 public bool Unequip(string heroId,EquipmentSlot slot){
  string key=EquipmentKey(heroId,slot);
  string previous;
  if(!EquippedItems.TryGetValue(key,out previous))return false;
  EquippedItems.Remove(key);
  AddEquipment(previous,1);
  return true;
 }

 public int EquipmentPowerFor(string heroId){
  int total=0;
  foreach(EquipmentSlot slot in Enum.GetValues(typeof(EquipmentSlot))){
   string id;
   if(EquippedItems.TryGetValue(EquipmentKey(heroId,slot),out id)){
    var item=EquipmentCatalog.Get(id);
    if(item!=null)total+=item.Power;
   }
  }
  return total;
 }

 public bool ClaimQuest(string questId){
  if(ClaimedQuestIds.Contains(questId))return false;
  var quest=QuestCatalog.Get(questId);
  if(quest==null||MetricValue(quest.Metric)<quest.Target)return false;
  ApplyReward(quest.Reward);
  ClaimedQuestIds.Add(questId);
  return true;
 }

 public RewardBundle ClaimDaily(DateTime now){
  var day=now.Date;
  if(LastDailyClaimUtc!=DateTime.MinValue&&LastDailyClaimUtc.Date==day)return null;
  int index=Math.Max(1,Math.Min(7,DailyRewardDay));
  var reward=DailyRewardCatalog.Cycle[index-1].Reward;
  ApplyReward(reward);
  LastDailyClaimUtc=day;
  DailyRewardDay=index==7?1:index+1;
  return reward;
 }

 public bool ClaimMail(string mailId){
  if(ClaimedMailIds.Contains(mailId))return false;
  var mail=LaunchMailCatalog.All.FirstOrDefault(m=>m.Id==mailId);
  if(mail==null)return false;
  ApplyReward(mail.Reward);
  ClaimedMailIds.Add(mailId);
  return true;
 }

 public bool ClaimAchievement(string achievementId){
  if(ClaimedAchievementIds.Contains(achievementId))return false;
  var achievement=AchievementCatalog.All.FirstOrDefault(a=>a.Id==achievementId);
  if(achievement==null||MetricValue(achievement.Metric)<achievement.Target)return false;
  ApplyReward(achievement.Reward);
  ClaimedAchievementIds.Add(achievementId);
  return true;
 }

 public bool FightTower(){
  int index=Math.Max(0,Math.Min(TowerCatalog.Floors.Length-1,HighestTowerFloor-1));
  var floor=TowerCatalog.Floors[index];
  if(TeamPower()<floor.EnemyPower)return false;
  ApplyReward(floor.Reward);
  IncrementMetric("tower_clears");
  if(HighestTowerFloor<TowerCatalog.Floors.Length)HighestTowerFloor++;
  return true;
 }

 public bool FightBoss(string bossId){
  if(ClaimedBossIds.Contains(bossId))return false;
  var boss=BossCatalog.Get(bossId);
  if(boss==null||TeamPower()<boss.RecommendedPower)return false;
  ApplyReward(boss.Reward);
  ClaimedBossIds.Add(bossId);
  IncrementMetric("boss_clears");
  return true;
 }

 public int TeamPower(){
  int total=0;
  foreach(var heroId in Formation.Slots)total+=BattleSimulator.HeroPower(Heroes[heroId])+EquipmentPowerFor(heroId);
  return total;
 }

 public int MetricValue(string metric){
  switch(metric){
   case "highest_stage": return HighestStage;
   case "heroes_owned": return Heroes.Count;
   case "tower_clears": return Math.Max(Metric("tower_clears"),HighestTowerFloor-1);
   default: return Metric(metric);
  }
 }

 public void GrantForMigration(int shards,IDictionary<string,int> equipment){
  if(shards>0)AscensionShards+=shards;
  if(equipment==null)return;
  foreach(var pair in equipment)if(pair.Value>0&&EquipmentCatalog.Get(pair.Key)!=null)AddEquipment(pair.Key,pair.Value);
 }

 void ApplyReward(RewardBundle reward){
  if(reward==null)return;
  Gold=Math.Max(0,Gold+Math.Max(0,reward.Gold));
  Gems=Math.Max(0,Gems+Math.Max(0,reward.Gems));
  AscensionShards=Math.Max(0,AscensionShards+Math.Max(0,reward.AscensionShards));
  if(!string.IsNullOrEmpty(reward.EquipmentId)&&EquipmentCatalog.Get(reward.EquipmentId)!=null)AddEquipment(reward.EquipmentId,1);
 }

 void AddEquipment(string id,int amount){
  int existing;
  EquipmentInventory.TryGetValue(id,out existing);
  EquipmentInventory[id]=Math.Max(0,existing+Math.Max(0,amount));
 }

 void IncrementMetric(string metric,int amount=1){
  int current;
  Metrics.TryGetValue(metric,out current);
  Metrics[metric]=Math.Max(0,current+Math.Max(0,amount));
 }

 int Metric(string metric){int value;return Metrics.TryGetValue(metric,out value)?value:0;}
 static int DuplicateShardValue(HeroRarity rarity){return rarity==HeroRarity.Legendary?25:rarity==HeroRarity.Epic?12:5;}
 static string EquipmentKey(string heroId,EquipmentSlot slot){return heroId+"|"+slot;}
}
}
