using System; using System.Linq; using System.Collections.Generic; using NUnit.Framework; using IdleSlime.Core;
public class IdleSlimeDomainTests {
[Test] public void Has12Heroes(){Assert.AreEqual(12,HeroCatalog.All.Length);Assert.AreEqual(12,HeroCatalog.All.Select(x=>x.Id).Distinct().Count());}
[Test] public void FormationIsExactly5Unique(){Assert.DoesNotThrow(()=>new Formation(HeroCatalog.All.Take(5).Select(x=>x.Id)));Assert.Throws<ArgumentException>(()=>new Formation(HeroCatalog.All.Take(4).Select(x=>x.Id)));Assert.Throws<ArgumentException>(()=>new Formation(new[]{"cinder","cinder","maris","briar","nyx"}));}
[Test] public void Has50IncreasingStages(){Assert.AreEqual(CampaignCatalog.MaxStage,CampaignCatalog.Stages.Length);Assert.AreEqual(50,CampaignCatalog.Stages.Length);for(int i=1;i<CampaignCatalog.Stages.Length;i++)Assert.Greater(CampaignCatalog.Stages[i].EnemyPower,CampaignCatalog.Stages[i-1].EnemyPower);}
[Test] public void BattleDeterministic(){var f=new Formation(HeroCatalog.All.Take(5).Select(x=>x.Id));var r=f.Slots.ToDictionary(x=>x,x=>new HeroState(x));var a=BattleSimulator.Resolve(f,r,CampaignCatalog.Stages[0]);var b=BattleSimulator.Resolve(f,r,CampaignCatalog.Stages[0]);Assert.AreEqual(a.TeamPower,b.TeamPower);Assert.AreEqual(a.Victory,b.Victory);}
[Test] public void UpgradedTeamWinsAndGetsRewards(){var f=new Formation(HeroCatalog.All.Take(5).Select(x=>x.Id));var r=f.Slots.ToDictionary(x=>x,x=>new HeroState(x){Level=30});var z=BattleSimulator.Resolve(f,r,CampaignCatalog.Stages[0]);Assert.IsTrue(z.Victory);Assert.Greater(z.Gold,0);Assert.Greater(z.HeroXp,0);}
[Test] public void LevelConsumesGold(){var h=new HeroState("cinder");int g=1000;Assert.IsTrue(Progression.TryLevel(h,ref g));Assert.AreEqual(2,h.Level);Assert.Less(g,1000);}
[Test] public void StarRulesMatchRarityCapsAndEvolutionBreakpoints(){
 Assert.AreEqual(3,StarRules.StartingStars(HeroRarity.Rare));Assert.AreEqual(5,StarRules.MaxStars(HeroRarity.Rare));
 Assert.AreEqual(4,StarRules.StartingStars(HeroRarity.Epic));Assert.AreEqual(8,StarRules.MaxStars(HeroRarity.Epic));
 Assert.AreEqual(5,StarRules.StartingStars(HeroRarity.Legendary));Assert.AreEqual(11,StarRules.MaxStars(HeroRarity.Legendary));
 Assert.AreEqual(6,StarRules.StartingStars(HeroRarity.Mythic));Assert.AreEqual(15,StarRules.MaxStars(HeroRarity.Mythic));
 Assert.AreEqual(0,StarRules.VisualEvolutionStage(HeroRarity.Legendary,7));Assert.AreEqual(1,StarRules.VisualEvolutionStage(HeroRarity.Legendary,8));Assert.AreEqual(2,StarRules.VisualEvolutionStage(HeroRarity.Legendary,11));
 Assert.AreEqual(1,StarRules.VisualEvolutionStage(HeroRarity.Mythic,8));Assert.AreEqual(2,StarRules.VisualEvolutionStage(HeroRarity.Mythic,11));Assert.AreEqual(3,StarRules.VisualEvolutionStage(HeroRarity.Mythic,13));Assert.AreEqual(4,StarRules.VisualEvolutionStage(HeroRarity.Mythic,15));
}
[Test] public void StarUpConsumesCopiesAndFodder(){
 var s=new IdleSlimeSession(DateTime.UtcNow);
 s.GrantDuplicateCopies("cinder",1);
 s.GrantFodder(HeroFaction.Tide,HeroRarity.Epic,5,2);
 var h=s.Heroes["cinder"];Assert.AreEqual(5,h.Stars);
 Assert.IsTrue(s.TryStarUp("cinder"));Assert.AreEqual(6,h.Stars);Assert.AreEqual(0,s.DuplicateCopies("cinder"));
}
[Test] public void DuplicateSummonCreatesDuplicateCopyInsteadOfAscensionShards(){
 var s=new IdleSlimeSession(DateTime.UtcNow);
 int before=s.DuplicateCopies("cinder");
 s.ApplySummonResult(HeroCatalog.Get("cinder"));
 Assert.AreEqual(before+1,s.DuplicateCopies("cinder"));
}
[Test] public void IdleCaps12Hours(){var z=IdleRewards.Calculate(TimeSpan.FromHours(30),20);Assert.AreEqual(720,z.Minutes);Assert.Greater(z.Gold,0);}
}
