using System; using System.Collections.Generic; using System.Linq;
namespace IdleSlime.Core {
public sealed class IdleSlimeSession {
 public readonly Dictionary<string,HeroState> Heroes=new Dictionary<string,HeroState>(); public Formation Formation{get;private set;} public int Gold{get;private set;} public int Gems{get;private set;} public int HighestStage{get;private set;}=1; public DateTime LastSeenUtc{get;private set;}
 public IdleSlimeSession(DateTime now){LastSeenUtc=now;foreach(var h in HeroCatalog.All.Take(5))Heroes[h.Id]=new HeroState(h.Id);Formation=new Formation(Heroes.Keys.Take(5));Gold=500;Gems=600;}
 public IdleReward ClaimIdle(DateTime now){var r=IdleRewards.Calculate(now-LastSeenUtc,HighestStage);Gold+=r.Gold;LastSeenUtc=now;return r;}
 public BattleResult Fight(){var s=CampaignCatalog.Stages[Math.Max(0,Math.Min(19,HighestStage-1))];var r=BattleSimulator.Resolve(Formation,Heroes,s);if(r.Victory){Gold+=r.Gold;Gems+=r.Gems;if(HighestStage<20)HighestStage++;}return r;}
 public bool Upgrade(string id){HeroState h;if(!Heroes.TryGetValue(id,out h))return false;int g=Gold;if(!Progression.TryLevel(h,ref g))return false;Gold=g;return true;}
 public HeroDefinition Summon(IRandomSource rng){if(Gems<Summoning.SingleCost)return null;Gems-=Summoning.SingleCost;var h=Summoning.Roll(rng);if(!Heroes.ContainsKey(h.Id))Heroes[h.Id]=new HeroState(h.Id);return h;}
 public void SetFormation(IEnumerable<string> ids){foreach(var id in ids)if(!Heroes.ContainsKey(id))throw new ArgumentException("Hero not owned: "+id);Formation=new Formation(ids);}
}
}
