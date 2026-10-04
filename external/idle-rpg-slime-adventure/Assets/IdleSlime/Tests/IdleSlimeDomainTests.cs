using System; using System.Linq; using System.Collections.Generic; using NUnit.Framework; using IdleSlime.Core;
public class IdleSlimeDomainTests {
[Test] public void Has12Heroes(){Assert.AreEqual(12,HeroCatalog.All.Length);Assert.AreEqual(12,HeroCatalog.All.Select(x=>x.Id).Distinct().Count());}
[Test] public void FormationIsExactly5Unique(){Assert.DoesNotThrow(()=>new Formation(HeroCatalog.All.Take(5).Select(x=>x.Id)));Assert.Throws<ArgumentException>(()=>new Formation(HeroCatalog.All.Take(4).Select(x=>x.Id)));Assert.Throws<ArgumentException>(()=>new Formation(new[]{"cinder","cinder","maris","briar","nyx"}));}
[Test] public void Has20IncreasingStages(){Assert.AreEqual(20,CampaignCatalog.Stages.Length);for(int i=1;i<20;i++)Assert.Greater(CampaignCatalog.Stages[i].EnemyPower,CampaignCatalog.Stages[i-1].EnemyPower);}
[Test] public void BattleDeterministic(){var f=new Formation(HeroCatalog.All.Take(5).Select(x=>x.Id));var r=f.Slots.ToDictionary(x=>x,x=>new HeroState(x));var a=BattleSimulator.Resolve(f,r,CampaignCatalog.Stages[0]);var b=BattleSimulator.Resolve(f,r,CampaignCatalog.Stages[0]);Assert.AreEqual(a.TeamPower,b.TeamPower);Assert.AreEqual(a.Victory,b.Victory);}
[Test] public void UpgradedTeamWinsAndGetsRewards(){var f=new Formation(HeroCatalog.All.Take(5).Select(x=>x.Id));var r=f.Slots.ToDictionary(x=>x,x=>new HeroState(x){Level=30});var z=BattleSimulator.Resolve(f,r,CampaignCatalog.Stages[0]);Assert.IsTrue(z.Victory);Assert.Greater(z.Gold,0);Assert.Greater(z.HeroXp,0);}
[Test] public void LevelConsumesGold(){var h=new HeroState("cinder");int g=1000;Assert.IsTrue(Progression.TryLevel(h,ref g));Assert.AreEqual(2,h.Level);Assert.Less(g,1000);}
[Test] public void IdleCaps12Hours(){var z=IdleRewards.Calculate(TimeSpan.FromHours(30),20);Assert.AreEqual(720,z.Minutes);Assert.Greater(z.Gold,0);}
}
