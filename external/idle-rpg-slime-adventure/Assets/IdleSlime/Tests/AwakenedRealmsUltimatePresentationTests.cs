using System;
using System.Linq;
using NUnit.Framework;
using IdleSlime.Core;

public sealed class AwakenedRealmsUltimatePresentationTests {
 [Test] public void EveryHeroHasALoreBoundUltimatePresentation(){
  Assert.AreEqual(HeroCatalog.All.Length,AwakenedRealmsUltimatePresentation.All.Length);
  foreach(var hero in HeroCatalog.All){
   var p=AwakenedRealmsUltimatePresentation.ForHero(hero.Id);
   Assert.IsNotNull(p,hero.Id);
   Assert.AreSame(hero,p.Hero);
   Assert.AreEqual(hero.Id,p.HeroId);
   Assert.IsNotNull(p.UltimateSkill,hero.Id+" needs an ultimate skill.");
   Assert.AreEqual(SkillKind.Ultimate,p.UltimateSkill.Kind);
   Assert.AreEqual(hero.Id,p.UltimateSkill.HeroId);
   Assert.IsNotNull(p.Destiny,hero.Id+" should keep a first-timeline destiny.");
   Assert.IsNotNull(p.FactionToken);
   Assert.IsNotNull(p.RarityToken);
   Assert.AreEqual(hero.Faction,p.FactionToken.Faction);
   Assert.AreEqual(hero.Rarity,p.RarityToken.Rarity);
   Assert.IsFalse(string.IsNullOrWhiteSpace(p.SignatureName));
   Assert.IsFalse(string.IsNullOrWhiteSpace(p.SignatureLine));
   Assert.IsFalse(string.IsNullOrWhiteSpace(p.SystemAlert));
   Assert.IsFalse(string.IsNullOrWhiteSpace(p.FateFragment));
   Assert.IsFalse(string.IsNullOrWhiteSpace(p.FinisherLine));
   Assert.IsFalse(string.IsNullOrWhiteSpace(p.RecoveryMotif));
   Assert.IsFalse(string.IsNullOrWhiteSpace(p.CutInGlyph));
  }
 }

 [Test] public void SignaturesAreUniqueAndNamed(){
  var names=AwakenedRealmsUltimatePresentation.All.Select(x=>x.SignatureName).ToArray();
  Assert.AreEqual(names.Length,names.Distinct().Count(),"Ultimate signature names must be unique.");
  var lines=AwakenedRealmsUltimatePresentation.All.Select(x=>x.SignatureLine).ToArray();
  Assert.AreEqual(lines.Length,lines.Distinct().Count(),"Signature lines must be unique.");
  foreach(var p in AwakenedRealmsUltimatePresentation.All)
   StringAssert.Contains(":",p.SignatureName,p.HeroId+" signature should read as a titled set piece.");
 }

 [Test] public void DestinyBindsEverySetPiece(){
  foreach(var p in AwakenedRealmsUltimatePresentation.All){
   var d=AwakenedRealmsNarrative.ForHero(p.HeroId);
   Assert.IsNotNull(d,p.HeroId);
   Assert.AreSame(d,p.Destiny);
   // The set piece must quote the established first-timeline fate verbatim.
   Assert.AreEqual(d.FirstTimelineFate,p.FateFragment,p.HeroId+" fate fragment must match narrative destiny.");
   // Signature names carry the first-timeline title so the ultimate is unmistakably lore-bound.
   StringAssert.Contains(d.FirstTimelineTitle.ToUpperInvariant().Split(' ')[0],p.SignatureName,p.HeroId+" signature should carry the destiny title.");
  }
 }

 [Test] public void FactionAndEchoMotifsArePresent(){
  foreach(var p in AwakenedRealmsUltimatePresentation.All){
   Assert.IsTrue(p.CutInGlyph.Contains(p.FactionToken.Sigil),p.HeroId+" cut-in must carry the faction sigil.");
   Assert.IsTrue(p.CutInGlyph.Contains(p.Hero.Name.Substring(0,1).ToUpperInvariant()),p.HeroId+" cut-in must carry the hero monogram.");
   // System alert uses the established Realm interface bracket language.
   Assert.IsTrue(p.SystemAlert.StartsWith("[",StringComparison.Ordinal)&&p.SystemAlert.EndsWith("]",StringComparison.Ordinal),p.HeroId+" system alert must read like a Realm message.");
   Assert.IsTrue(p.EnvironmentCues.Length>=2,p.HeroId+" needs multiple environment response hooks.");
   Assert.IsTrue(p.EnvironmentCues.All(c=>!string.IsNullOrWhiteSpace(c.Hook)&&c.Intensity>0f&&c.Intensity<=1f),p.HeroId+" cues must be named and bounded.");
  }
 }

 [Test] public void PhaseOrderIsCanonicalAndComplete(){
  var expected=new[]{UltimatePhase.Anticipation,UltimatePhase.CutIn,UltimatePhase.TimeDilation,UltimatePhase.Impact,UltimatePhase.EnvironmentResponse,UltimatePhase.Finisher,UltimatePhase.Recovery};
  foreach(var p in AwakenedRealmsUltimatePresentation.All)
   CollectionAssert.AreEqual(expected,p.PhaseOrder,p.HeroId+" phase order must stay canonical.");
  Assert.AreEqual(expected.Length,Enum.GetValues(typeof(UltimatePhase)).Length,"UltimatePhase must stay aligned with the canonical set-piece order.");
 }

 [Test] public void TimingAndScaleStayPresentationalOnly(){
  foreach(var p in AwakenedRealmsUltimatePresentation.All){
   Assert.IsTrue(p.FreezeSeconds>=0.25f&&p.FreezeSeconds<=0.9f,p.HeroId+" freeze window should stay cinematic but bounded.");
   Assert.IsTrue(p.AfterimageCount>=2&&p.AfterimageCount<=10,p.HeroId+" afterimage count should be anime-scale but bounded.");
   Assert.IsTrue(p.ShakeAmplitude>=5f&&p.ShakeAmplitude<=16f,p.HeroId+" shake should read but not rupture the layout.");
   Assert.IsTrue(p.ImpactBeats.Length>=2,p.HeroId+" needs staged impact beats.");
   Assert.IsTrue(p.ImpactBeats.All(b=>!string.IsNullOrWhiteSpace(b.Id)&&!string.IsNullOrWhiteSpace(b.Motion)&&b.HitCount>=1),p.HeroId+" beats must be named.");
   foreach(UltimatePhase phase in Enum.GetValues(typeof(UltimatePhase)))
    Assert.Greater(p.PhaseDuration(phase),0f,p.HeroId+" "+phase+" duration must stay positive.");
  }
 }

 [Test] public void CatalogLookupIsDeterministic(){
  foreach(var hero in HeroCatalog.All){
   var a=AwakenedRealmsUltimatePresentation.ForHero(hero.Id);
   var b=AwakenedRealmsUltimatePresentation.ForHero(hero.Id);
   Assert.AreSame(a,b,hero.Id+" lookup must return the same instance.");
   var byName=AwakenedRealmsUltimatePresentation.ForHeroName(hero.Name);
   Assert.AreSame(a,byName,hero.Id+" name lookup must resolve to the same presentation.");
  }
  Assert.IsNull(AwakenedRealmsUltimatePresentation.ForHero("unknown_hero"));
  Assert.IsNull(AwakenedRealmsUltimatePresentation.ForHero(null));
  Assert.IsNull(AwakenedRealmsUltimatePresentation.ForHeroName("Nobody"));
 }

 [Test] public void BattlePresentationCanResolveEveryHeroByName(){
  // BattlePresentationPlan links actor names to HeroIds; the name-based lookup must
  // resolve for every hero so skill beats always bind a set piece at runtime.
  foreach(var hero in HeroCatalog.All){
   var p=AwakenedRealmsUltimatePresentation.ForHeroName(hero.Name);
   Assert.IsNotNull(p,hero.Name);
   Assert.AreEqual(hero.Id,p.HeroId);
  }
 }

 [Test] public void UltimateSkillsMatchTheSkillCatalogContract(){
  // The set piece rides on the authoritative skill definition, never a copy.
  foreach(var p in AwakenedRealmsUltimatePresentation.All){
   var catalog=SkillCatalog.ForHero(p.HeroId).FirstOrDefault(x=>x.Kind==SkillKind.Ultimate);
   Assert.IsNotNull(catalog,p.HeroId);
   Assert.AreSame(catalog,p.UltimateSkill,p.HeroId+" ultimate must be the catalog instance.");
   Assert.Greater(catalog.PowerPercent,0);
   Assert.AreEqual(1,catalog.UnlockAscension,p.HeroId+" ultimates unlock at ascension 1 per catalog contract.");
  }
 }
}
