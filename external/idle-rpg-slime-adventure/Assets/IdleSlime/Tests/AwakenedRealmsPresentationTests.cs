using System;
using System.Linq;
using NUnit.Framework;
using IdleSlime.Core;

public sealed class AwakenedRealmsPresentationTests {
 [Test] public void EveryFactionHasABespokeVisualToken(){
  foreach(HeroFaction faction in Enum.GetValues(typeof(HeroFaction))){
   var token=AwakenedRealmsVisualTheme.Faction(faction);
   Assert.IsNotNull(token,faction.ToString());
   Assert.IsFalse(string.IsNullOrWhiteSpace(token.DisplayName));
   Assert.IsFalse(string.IsNullOrWhiteSpace(token.Sigil));
   Assert.IsFalse(string.IsNullOrWhiteSpace(token.Motto));
  }
  Assert.AreEqual(Enum.GetValues(typeof(HeroFaction)).Length,AwakenedRealmsVisualTheme.FactionTokens.Count);
  Assert.IsTrue(AwakenedRealmsVisualTheme.FactionTokens.Select(x=>x.Sigil).Distinct().Count()==AwakenedRealmsVisualTheme.FactionTokens.Count,"Sigils must be unique.");
  Assert.IsTrue(AwakenedRealmsVisualTheme.FactionTokens.Select(x=>x.Core.Hex).Distinct().Count()==AwakenedRealmsVisualTheme.FactionTokens.Count,"Core colors must be unique.");
 }

 [Test] public void EveryRarityHasAnEchoVisualToken(){
  foreach(HeroRarity rarity in Enum.GetValues(typeof(HeroRarity))){
   var token=AwakenedRealmsVisualTheme.Rarity(rarity);
   Assert.IsNotNull(token,rarity.ToString());
   Assert.AreEqual((int)rarity,token.StarCount,"Star count should mirror the rarity tier value.");
   Assert.IsTrue(token.FrameLayers>=1&&token.FrameLayers<=3);
   Assert.IsTrue(token.PulseScale>=0f&&token.PulseScale<=MotionTokens.RarityPulseScale+0.001f);
  }
  var legendary=AwakenedRealmsVisualTheme.Rarity(HeroRarity.Legendary);
  Assert.AreEqual("SOVEREIGN ECHO",legendary.EchoLabel);
  Assert.AreEqual(EchoLanguage.SovereignMark,legendary.Crest);
 }

 [Test] public void EveryHeroResolvesAFullPresentation(){
  Assert.AreEqual(HeroCatalog.All.Length,AwakenedRealmsVisualTheme.AllPresentations().Count());
  foreach(var hero in HeroCatalog.All){
   var p=AwakenedRealmsVisualTheme.Presentation(hero.Id);
   Assert.IsNotNull(p,hero.Id);
   Assert.AreSame(hero,p.Definition);
   Assert.IsNotNull(p.FactionToken);
   Assert.IsNotNull(p.RarityToken);
   Assert.IsNotNull(p.Destiny,hero.Id+" should keep a first-timeline destiny.");
   Assert.AreEqual(p.Destiny.FirstTimelineTitle,p.BannerTitle);
   Assert.AreEqual(hero.Name.Substring(0,1),p.Monogram);
   Assert.AreEqual(p.FactionToken.Sigil,p.PortraitGlyph);
   Assert.IsFalse(string.IsNullOrWhiteSpace(p.SignatureLine));
  }
 }

 [Test] public void PanelStylesExposeLayeredHooksInDrawOrder(){
  var required=new[]{"panel_base","card_standard","card_rarity","banner_hero","echo_realm"};
  foreach(var key in required){
   var style=AwakenedRealmsVisualTheme.Style(key);
   Assert.IsNotNull(style,key);
   Assert.IsTrue(style.Layers.Length>=3,key+" should be layered.");
   for(int i=1;i<style.Layers.Length;i++)
    Assert.Greater(style.Layers[i].InsetPixels,style.Layers[i-1].InsetPixels,key+" layers must nest inward.");
   Assert.IsTrue(style.Layers.Select(l=>l.Key).Distinct().Count()==style.Layers.Length,key+" layer keys must be unique.");
  }
  var rarity=AwakenedRealmsVisualTheme.Style("card_rarity");
  Assert.IsNotNull(rarity.Layer("glow"));
  Assert.IsNotNull(rarity.Layer("sheen"));
 }

 [Test] public void ThemeColorsRejectMalformedHex(){
  Assert.Throws<ArgumentException>(()=>new ThemeColor(""));
  Assert.Throws<ArgumentException>(()=>new ThemeColor("12345"));
  Assert.Throws<ArgumentException>(()=>new ThemeColor("#1234567890"));
  var c=new ThemeColor("57e6d4");
  Assert.AreEqual("#57E6D4",c.Hex);
  Assert.AreEqual("#57E6D4",c.RgbHex);
  Assert.IsFalse(c.HasAlpha);
  var a=new ThemeColor("#57E6D480");
  Assert.IsTrue(a.HasAlpha);
 }

 [Test] public void PresentationPreservesNarrativeVisualKeys(){
  // The presentation layer consumes VisualKey hooks; every stage must keep one so CG/banner binding stays lossless.
  Assert.IsTrue(AwakenedRealmsNarrative.Beats.All(x=>!string.IsNullOrWhiteSpace(x.VisualKey)));
  Assert.IsTrue(AwakenedRealmsNarrative.Beats.Select(x=>x.VisualKey).Distinct().Count()==AwakenedRealmsNarrative.Beats.Length,"Each stage should carry a distinct visual hook.");
  foreach(var beat in AwakenedRealmsNarrative.Beats)
   Assert.IsTrue(beat.VisualKey.StartsWith("cg_",StringComparison.Ordinal),beat.VisualKey+" should use the cinematic hook prefix.");
 }

 [Test] public void EchoLanguageGlyphsAreStable(){
  Assert.AreEqual("✦",EchoLanguage.EchoMark);
  Assert.AreEqual("◈",EchoLanguage.ResonanceMark);
  Assert.AreEqual("⟁",EchoLanguage.FractureMark);
  Assert.AreEqual("♛",EchoLanguage.SovereignMark);
  Assert.AreEqual("◆",EchoLanguage.Divider);
  Assert.IsTrue(MotionTokens.EntranceStagger>0f&&MotionTokens.EntranceStagger<0.2f);
  Assert.IsTrue(MotionTokens.PanelReveal>0.1f&&MotionTokens.PanelReveal<1f);
 }
}
