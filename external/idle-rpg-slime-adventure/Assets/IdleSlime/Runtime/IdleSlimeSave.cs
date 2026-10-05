using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using IdleSlime.Core;
using UnityEngine;

namespace IdleSlime.Runtime {
public static class IdleSlimeSave {
 const int Version=3;
 const string Key="awakened_realms_idle_rpg_save_v1";

 [Serializable] sealed class HeroSave { public string id; public int level; public int ascension; public int stars; }
 [Serializable] sealed class KeyInt { public string key; public int value; }
 [Serializable] sealed class KeyString { public string key; public string value; }

 [Serializable] sealed class SaveData {
  public int version;
  public int gold;
  public int gems;
  public int ascensionShards;
  public KeyInt[] duplicateHeroCopies;
  public KeyInt[] fodderInventory;
  public int highestStage;
  public int highestTowerFloor;
  public int dailyRewardDay;
  public long lastSeenTicks;
  public long lastDailyClaimTicks;
  public HeroSave[] heroes;
  public string[] formation;
  public KeyInt[] equipmentInventory;
  public KeyString[] equippedItems;
  public string[] claimedQuestIds;
  public string[] claimedAchievementIds;
  public string[] claimedMailIds;
  public string[] claimedBossIds;
  public KeyInt[] metrics;
 }

 static readonly BindingFlags Flags=BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic;

 public static IdleSlimeSession LoadOrCreate(DateTime now){
  try{
   var raw=PlayerPrefs.GetString(Key,"");
   if(string.IsNullOrEmpty(raw))return new IdleSlimeSession(now);
   var d=JsonUtility.FromJson<SaveData>(raw);
   Validate(d);

   var s=new IdleSlimeSession(now);
   s.Heroes.Clear();
   foreach(var h in d.heroes){
    var definition=HeroCatalog.Get(h.id);
    int migratedStars=d.version>=3?h.stars:StarRules.StartingStars(definition.Rarity)+Math.Max(0,h.ascension);
    s.Heroes[h.id]=new HeroState(h.id){Level=h.level,Stars=StarRules.ClampStars(definition.Rarity,migratedStars)};
   }
   s.SetFormation(d.formation);

   Set(s,"Gold",d.gold);
   Set(s,"Gems",d.gems);
   Set(s,"HighestStage",d.highestStage);
   Set(s,"LastSeenUtc",new DateTime(d.lastSeenTicks,DateTimeKind.Utc));

   if(d.version>=2){
    Set(s,"AscensionShards",Math.Max(0,d.ascensionShards));
    Set(s,"HighestTowerFloor",Math.Max(1,Math.Min(TowerCatalog.Floors.Length,d.highestTowerFloor<=0?1:d.highestTowerFloor)));
    Set(s,"DailyRewardDay",Math.Max(1,Math.Min(7,d.dailyRewardDay<=0?1:d.dailyRewardDay)));
    if(d.lastDailyClaimTicks>0)Set(s,"LastDailyClaimUtc",new DateTime(d.lastDailyClaimTicks,DateTimeKind.Utc));

    RestoreKeyInts(s.EquipmentInventory,d.equipmentInventory,id=>EquipmentCatalog.Get(id)!=null);
    RestoreKeyStrings(s.EquippedItems,d.equippedItems);
    RestoreSet(s.ClaimedQuestIds,d.claimedQuestIds);
    RestoreSet(s.ClaimedAchievementIds,d.claimedAchievementIds);
    RestoreSet(s.ClaimedMailIds,d.claimedMailIds);
    RestoreSet(s.ClaimedBossIds,d.claimedBossIds);
    RestoreKeyInts(s.Metrics,d.metrics,_=>true);
   }
   if(d.version>=3){
    RestoreKeyInts(s.DuplicateHeroCopies,d.duplicateHeroCopies,id=>HeroCatalog.Get(id)!=null);
    RestoreKeyInts(s.FodderInventory,d.fodderInventory,IsValidFodderKey);
   }
   return s;
  }catch(Exception e){
   Debug.LogWarning("[AwakenedRealms] Save rejected; starting fresh: "+e.Message);
   return new IdleSlimeSession(now);
  }
 }

 public static void Save(IdleSlimeSession s){
  if(s==null)return;
  var d=new SaveData{
   version=Version,
   gold=s.Gold,
   gems=s.Gems,
   ascensionShards=s.AscensionShards,
   duplicateHeroCopies=s.DuplicateHeroCopies.Select(p=>new KeyInt{key=p.Key,value=p.Value}).ToArray(),
   fodderInventory=s.FodderInventory.Select(p=>new KeyInt{key=p.Key,value=p.Value}).ToArray(),
   highestStage=s.HighestStage,
   highestTowerFloor=s.HighestTowerFloor,
   dailyRewardDay=s.DailyRewardDay,
   lastSeenTicks=s.LastSeenUtc.Ticks,
   lastDailyClaimTicks=s.LastDailyClaimUtc==DateTime.MinValue?0:s.LastDailyClaimUtc.Ticks,
   heroes=s.Heroes.Values.Select(h=>new HeroSave{id=h.HeroId,level=h.Level,ascension=0,stars=h.Stars}).ToArray(),
   formation=s.Formation.Slots.ToArray(),
   equipmentInventory=s.EquipmentInventory.Select(p=>new KeyInt{key=p.Key,value=p.Value}).ToArray(),
   equippedItems=s.EquippedItems.Select(p=>new KeyString{key=p.Key,value=p.Value}).ToArray(),
   claimedQuestIds=s.ClaimedQuestIds.ToArray(),
   claimedAchievementIds=s.ClaimedAchievementIds.ToArray(),
   claimedMailIds=s.ClaimedMailIds.ToArray(),
   claimedBossIds=s.ClaimedBossIds.ToArray(),
   metrics=s.Metrics.Select(p=>new KeyInt{key=p.Key,value=p.Value}).ToArray()
  };
  PlayerPrefs.SetString(Key,JsonUtility.ToJson(d));
  PlayerPrefs.Save();
 }

 static void Validate(SaveData d){
  if(d==null||(d.version!=1&&d.version!=2&&d.version!=Version))throw new InvalidOperationException("unsupported save version");
  if(d.gold<0||d.gems<0||d.highestStage<1||d.highestStage>CampaignCatalog.MaxStage)throw new InvalidOperationException("invalid progression values");
  if(d.heroes==null||d.heroes.Length<5||d.heroes.Any(h=>h==null||HeroCatalog.Get(h.id)==null||h.level<1||h.level>10000||!ValidHeroProgression(d.version,h)))throw new InvalidOperationException("invalid hero roster");
  if(d.heroes.Select(h=>h.id).Distinct().Count()!=d.heroes.Length)throw new InvalidOperationException("duplicate hero state");
  if(d.formation==null||d.formation.Length!=5||d.formation.Distinct().Count()!=5||d.formation.Any(id=>!d.heroes.Any(h=>h.id==id)))throw new InvalidOperationException("invalid formation");
  if(d.lastSeenTicks<=0||d.lastSeenTicks>DateTime.UtcNow.AddMinutes(5).Ticks)throw new InvalidOperationException("invalid timestamp");

  if(d.version>=2){
   if(d.ascensionShards<0||d.highestTowerFloor<1||d.highestTowerFloor>TowerCatalog.Floors.Length||d.dailyRewardDay<1||d.dailyRewardDay>7)throw new InvalidOperationException("invalid extended progression values");
   if(d.lastDailyClaimTicks<0||d.lastDailyClaimTicks>DateTime.UtcNow.AddMinutes(5).Ticks)throw new InvalidOperationException("invalid daily timestamp");
   if(d.equipmentInventory!=null&&d.equipmentInventory.Any(x=>x==null||x.value<0||EquipmentCatalog.Get(x.key)==null))throw new InvalidOperationException("invalid equipment inventory");
   if(d.equippedItems!=null&&d.equippedItems.Any(x=>x==null||string.IsNullOrEmpty(x.key)||EquipmentCatalog.Get(x.value)==null))throw new InvalidOperationException("invalid equipped item");
   if(d.metrics!=null&&d.metrics.Any(x=>x==null||string.IsNullOrEmpty(x.key)||x.value<0))throw new InvalidOperationException("invalid metrics");
  }
 }

 static bool ValidHeroProgression(int version,HeroSave h){
  var definition=HeroCatalog.Get(h.id);
  if(definition==null)return false;
  if(version<3)return h.ascension>=0&&h.ascension<=AscensionRules.MaxAscension;
  return h.stars>=StarRules.StartingStars(definition.Rarity)&&h.stars<=StarRules.MaxStars(definition.Rarity);
 }

 static bool IsValidFodderKey(string key){
  if(string.IsNullOrEmpty(key))return false;
  var parts=key.Split('|');
  if(parts.Length!=3)return false;
  HeroFaction faction;HeroRarity rarity;int stars;
  if(!Enum.TryParse(parts[0],out faction)||!Enum.TryParse(parts[1],out rarity)||!int.TryParse(parts[2],out stars))return false;
  return stars>=StarRules.StartingStars(rarity)&&stars<=StarRules.MaxStars(rarity);
 }

 static void RestoreKeyInts(IDictionary<string,int> target,KeyInt[] values,Func<string,bool> keyAllowed){
  if(values==null)return;
  foreach(var pair in values)if(pair!=null&&!string.IsNullOrEmpty(pair.key)&&pair.value>=0&&keyAllowed(pair.key))target[pair.key]=pair.value;
 }

 static void RestoreKeyStrings(IDictionary<string,string> target,KeyString[] values){
  if(values==null)return;
  foreach(var pair in values){
   if(pair==null||string.IsNullOrEmpty(pair.key)||EquipmentCatalog.Get(pair.value)==null)continue;
   var split=pair.key.Split('|');
   if(split.Length!=2||HeroCatalog.Get(split[0])==null)continue;
   EquipmentSlot slot;
   if(!Enum.TryParse(split[1],out slot))continue;
   if(EquipmentCatalog.Get(pair.value).Slot!=slot)continue;
   target[pair.key]=pair.value;
  }
 }

 static void RestoreSet(ICollection<string> target,string[] values){
  if(values==null)return;
  foreach(var value in values)if(!string.IsNullOrEmpty(value)&&!target.Contains(value))target.Add(value);
 }

 static void Set(IdleSlimeSession s,string property,object value){
  var p=typeof(IdleSlimeSession).GetProperty(property,Flags);
  if(p==null)throw new MissingMemberException(property);
  p.SetValue(s,value,null);
 }
}
}
