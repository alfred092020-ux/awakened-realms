using System;
using System.Linq;
using System.Reflection;
using IdleSlime.Core;
using UnityEngine;
namespace IdleSlime.Runtime {
public static class IdleSlimeSave {
 const int Version=1; const string Key="awakened_realms_idle_rpg_save_v1";
 [Serializable] sealed class HeroSave { public string id; public int level; public int ascension; }
 [Serializable] sealed class SaveData { public int version; public int gold; public int gems; public int highestStage; public long lastSeenTicks; public HeroSave[] heroes; public string[] formation; }
 static readonly BindingFlags Flags=BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic;
 public static IdleSlimeSession LoadOrCreate(DateTime now){try{var raw=PlayerPrefs.GetString(Key,"");if(string.IsNullOrEmpty(raw))return new IdleSlimeSession(now);var d=JsonUtility.FromJson<SaveData>(raw);Validate(d);var s=new IdleSlimeSession(now);s.Heroes.Clear();foreach(var h in d.heroes)s.Heroes[h.id]=new HeroState(h.id){Level=h.level,Ascension=h.ascension};s.SetFormation(d.formation);Set(s,"Gold",d.gold);Set(s,"Gems",d.gems);Set(s,"HighestStage",d.highestStage);Set(s,"LastSeenUtc",new DateTime(d.lastSeenTicks,DateTimeKind.Utc));return s;}catch(Exception e){Debug.LogWarning("[AwakenedRealms] Save rejected; starting fresh: "+e.Message);return new IdleSlimeSession(now);}}
 public static void Save(IdleSlimeSession s){if(s==null)return;var d=new SaveData{version=Version,gold=s.Gold,gems=s.Gems,highestStage=s.HighestStage,lastSeenTicks=s.LastSeenUtc.Ticks,heroes=s.Heroes.Values.Select(h=>new HeroSave{id=h.HeroId,level=h.Level,ascension=h.Ascension}).ToArray(),formation=s.Formation.Slots.ToArray()};PlayerPrefs.SetString(Key,JsonUtility.ToJson(d));PlayerPrefs.Save();}
 static void Validate(SaveData d){if(d==null||d.version!=Version)throw new InvalidOperationException("unsupported save version");if(d.gold<0||d.gems<0||d.highestStage<1||d.highestStage>20)throw new InvalidOperationException("invalid progression values");if(d.heroes==null||d.heroes.Length<5||d.heroes.Any(h=>h==null||HeroCatalog.Get(h.id)==null||h.level<1||h.level>10000||h.ascension<0))throw new InvalidOperationException("invalid hero roster");if(d.heroes.Select(h=>h.id).Distinct().Count()!=d.heroes.Length)throw new InvalidOperationException("duplicate hero state");if(d.formation==null||d.formation.Length!=5||d.formation.Distinct().Count()!=5||d.formation.Any(id=>!d.heroes.Any(h=>h.id==id)))throw new InvalidOperationException("invalid formation");if(d.lastSeenTicks<=0||d.lastSeenTicks>DateTime.UtcNow.AddMinutes(5).Ticks)throw new InvalidOperationException("invalid timestamp");}
 static void Set(IdleSlimeSession s,string property,object value){var p=typeof(IdleSlimeSession).GetProperty(property,Flags);if(p==null)throw new MissingMemberException(property);p.SetValue(s,value,null);}
}
}