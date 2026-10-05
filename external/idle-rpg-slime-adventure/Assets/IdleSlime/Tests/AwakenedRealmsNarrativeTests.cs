using System.Linq;
using NUnit.Framework;
using IdleSlime.Core;

public sealed class AwakenedRealmsNarrativeTests {
 [Test] public void SeasonOneCoversEveryCampaignStage(){
  Assert.AreEqual(CampaignCatalog.MaxStage,AwakenedRealmsNarrative.Beats.Length);
  CollectionAssert.AreEquivalent(Enumerable.Range(1,CampaignCatalog.MaxStage),AwakenedRealmsNarrative.Beats.Select(x=>x.Stage));
  Assert.IsTrue(AwakenedRealmsNarrative.Beats.All(x=>!string.IsNullOrWhiteSpace(x.StageTitle)&&!string.IsNullOrWhiteSpace(x.Summary)&&!string.IsNullOrWhiteSpace(x.VisualKey)));
 }
 [Test] public void EveryHeroHasAFirstTimelineDestiny(){
  Assert.AreEqual(HeroCatalog.All.Length,AwakenedRealmsNarrative.Destinies.Length);
  foreach(var hero in HeroCatalog.All){
   var d=AwakenedRealmsNarrative.ForHero(hero.Id);
   Assert.IsNotNull(d,hero.Id);
   Assert.IsFalse(string.IsNullOrWhiteSpace(d.FirstTimelineFate));
   Assert.IsFalse(string.IsNullOrWhiteSpace(d.SecondTimelineHook));
  }
 }
 [Test] public void NarrativeUsesFiveTenStageArcs(){
  var arcs=AwakenedRealmsNarrative.Beats.GroupBy(x=>x.ArcId).OrderBy(x=>x.Key).ToArray();
  Assert.AreEqual(5,arcs.Length);
  Assert.IsTrue(arcs.All(x=>x.Count()==10));
 }
 [Test] public void FinaleEstablishesThirdTimelineHook(){
  var finale=AwakenedRealmsNarrative.ForStage(50);
  StringAssert.Contains("Third Timeline",finale.StageTitle);
  StringAssert.Contains("UNKNOWN TIMELINE",finale.SystemMessage);
 }
}
