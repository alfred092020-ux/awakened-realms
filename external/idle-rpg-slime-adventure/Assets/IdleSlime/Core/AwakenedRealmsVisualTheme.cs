using System;
using System.Collections.Generic;
using System.Linq;

namespace IdleSlime.Core {
 /// <summary>Hex-based visual token so presentation data stays Unity-free and fully testable.</summary>
 public struct ThemeColor : IEquatable<ThemeColor> {
  public readonly string Hex;
  public ThemeColor(string hex){
   if(string.IsNullOrWhiteSpace(hex))throw new ArgumentException("hex");
   string h=hex.Trim();
   if(h[0]=='#')h=h.Substring(1);
   if(h.Length!=6&&h.Length!=8)throw new ArgumentException("Expected RRGGBB or RRGGBBAA.",nameof(hex));
   Hex="#"+h.ToUpperInvariant();
  }
  public string RgbHex{get{return Hex.Substring(0,7);}}
  public bool HasAlpha{get{return Hex.Length==9;}}
  public bool Equals(ThemeColor other){return string.Equals(Hex,other.Hex,StringComparison.OrdinalIgnoreCase);}
  public override bool Equals(object obj){return obj is ThemeColor&&Equals((ThemeColor)obj);}
  public override int GetHashCode(){return StringComparer.OrdinalIgnoreCase.GetHashCode(Hex);}
  public override string ToString(){return Hex;}
  public static ThemeColor From(string hex){return new ThemeColor(hex);}
 }

 /// <summary>Bespoke faction identity. Sigils are the realm mark; threads are the Echo line each faction emits.</summary>
 public sealed class FactionVisualToken {
  public HeroFaction Faction{get;private set;}
  public string Key,DisplayName,Sigil,Motto;
  public ThemeColor Core,Aura,Thread,EmblemBackground;
  public FactionVisualToken(HeroFaction faction,string key,string displayName,string sigil,string motto,string core,string aura,string thread,string emblem){
   Faction=faction;Key=key;DisplayName=displayName;Sigil=sigil;Motto=motto;
   Core=new ThemeColor(core);Aura=new ThemeColor(aura);Thread=new ThemeColor(thread);EmblemBackground=new ThemeColor(emblem);
  }
 }

 /// <summary>Rarity is presented as Echo intensity, not generic gem colors. Star count stays aligned to the enum value.</summary>
 public sealed class RarityVisualToken {
  public HeroRarity Rarity{get;private set;}
  public string Key,DisplayName,EchoLabel,Crest;
  public ThemeColor Glow,Plate,Edge;
  public int StarCount,FrameLayers;
  public float PulseScale;
  public RarityVisualToken(HeroRarity rarity,string key,string displayName,string echoLabel,string crest,string glow,string plate,string edge,int stars,int layers,float pulse){
   Rarity=rarity;Key=key;DisplayName=displayName;EchoLabel=echoLabel;Crest=crest;
   Glow=new ThemeColor(glow);Plate=new ThemeColor(plate);Edge=new ThemeColor(edge);
   StarCount=stars;FrameLayers=layers;PulseScale=pulse;
  }
 }

 /// <summary>Layered panel/card styling hook. Each layer is a hook a Unity builder or DOTween pass can target.</summary>
 public sealed class PanelLayerSpec {
  public string Key{get;private set;}
  public ThemeColor Color{get;private set;}
  public float InsetPixels;
  public PanelLayerSpec(string key,string hex,float inset){Key=key;Color=new ThemeColor(hex);InsetPixels=inset;}
 }

 public sealed class PanelStyle {
  public string Key{get;private set;}
  public PanelLayerSpec[] Layers{get;private set;}
  public float CornerRadiusPx;
  public PanelStyle(string key,float radius,params PanelLayerSpec[] layers){Key=key;CornerRadiusPx=radius;Layers=layers;}
  public PanelLayerSpec Layer(string key){return Layers.FirstOrDefault(x=>x.Key==key);}
 }

 /// <summary>Everything the hero-detail presentation needs, joined from catalog, destiny, and theme.</summary>
 public sealed class HeroPresentation {
  public HeroDefinition Definition{get;private set;}
  public HeroDestiny Destiny{get;private set;}
  public FactionVisualToken FactionToken{get;private set;}
  public RarityVisualToken RarityToken{get;private set;}
  public string BannerTitle{get;private set;}
  public string Monogram{get;private set;}
  public string SignatureLine{get;private set;}
  public string PortraitGlyph{get;private set;}
  public HeroPresentation(HeroDefinition def,HeroDestiny destiny){
   if(def==null)throw new ArgumentNullException("def");
   Definition=def;Destiny=destiny;
   FactionToken=AwakenedRealmsVisualTheme.Faction(def.Faction);
   RarityToken=AwakenedRealmsVisualTheme.Rarity(def.Rarity);
   BannerTitle=destiny!=null?destiny.FirstTimelineTitle:"Unwritten Echo";
   Monogram=def.Name.Substring(0,1).ToUpperInvariant();
   SignatureLine=destiny!=null?destiny.SecondTimelineHook:def.Faction+" "+def.Role;
   PortraitGlyph=FactionToken.Sigil;
  }
 }

 /// <summary>Motion timing tokens shared with AwakenedRealmsPremiumMotion so Core stays testable.</summary>
 public static class MotionTokens {
  public const float EntranceStagger=0.045f;
  public const float PanelReveal=0.34f;
  public const float RarityPulseScale=0.035f;
  public const float DamagePopupRisePx=96f;
 }

 /// <summary>Shared glyphs for the Echo/Realm interface language.</summary>
 public static class EchoLanguage {
  public const string EchoMark="✦";
  public const string ResonanceMark="◈";
  public const string FractureMark="⟁";
  public const string SovereignMark="♛";
  public const string Divider="◆";
 }

 public static class AwakenedRealmsVisualTheme {
  public static readonly ThemeColor VoidBase=new ThemeColor("#080D18");
  public static readonly ThemeColor InkSurface=new ThemeColor("#0D1424");
  public static readonly ThemeColor Panel=new ThemeColor("#121B30");
  public static readonly ThemeColor PanelRaised=new ThemeColor("#18233C");
  public static readonly ThemeColor EchoCyan=new ThemeColor("#57E6D4");
  public static readonly ThemeColor SovereignGold=new ThemeColor("#F0B44C");
  public static readonly ThemeColor RealmSilver=new ThemeColor("#B8C6E0");
  public static readonly ThemeColor InkMuted=new ThemeColor("#7C89A6");
  public static readonly ThemeColor CollapseRed=new ThemeColor("#F4575E");
  public static readonly ThemeColor FractureViolet=new ThemeColor("#9A7BFF");
  public static readonly ThemeColor EnergyThread=new ThemeColor("#6C8DFF");
  public static readonly ThemeColor BannerInk=new ThemeColor("#0A0F1D");
  public static readonly ThemeColor EchoVeil=new ThemeColor("#57E6D417");

  static readonly FactionVisualToken[] factionTokens={
   new FactionVisualToken(HeroFaction.Ember,"ember","Ember Remnant","▲","The ash remembers the fire.","#FF8A3D","#FF4E2E","#FFB066","#2A140D"),
   new FactionVisualToken(HeroFaction.Tide,"tide","Tidebound Choir","◆","The drowned horizon still sings.","#3ED0FF","#1E7FE0","#7FE7FF","#0B1A2B"),
   new FactionVisualToken(HeroFaction.Verdant,"verdant","Worldroot Covenant","❖","Every root keeps a second memory.","#8BE15E","#3D9E57","#C2F08A","#12200F"),
   new FactionVisualToken(HeroFaction.Radiant,"radiant","Solar Heresy","✹","The halo was forged; the light is hers.","#FFD65A","#F49E2B","#FFEFA0","#241A09"),
   new FactionVisualToken(HeroFaction.Umbral,"umbral","Umbral Court","◐","The eclipse favors the patient.","#9A7BFF","#5D3FD6","#C9A9FF","#171029"),
  };

  static readonly RarityVisualToken[] rarityTokens={
   new RarityVisualToken(HeroRarity.Rare,"bound","Bound Echo","ECHO","◆","#6C8DFF","#182036","#5D6FAE",3,1,0f),
   new RarityVisualToken(HeroRarity.Epic,"awakened","Awakened Echo","ECHO RESONANT","◈","#B06CFF","#1D1633","#8D5DE0",4,2,0.02f),
   new RarityVisualToken(HeroRarity.Legendary,"sovereign","Sovereign Echo","SOVEREIGN ECHO","♛","#F0B44C","#2A1F0C","#E0A63C",5,3,0.035f),
  };

  static readonly PanelStyle[] panelStyles={
   new PanelStyle("panel_base",16f,
    new PanelLayerSpec("halo","#57E6D40F",0f),
    new PanelLayerSpec("body","#121B30",2f),
    new PanelLayerSpec("inner","#0D1424",8f)),
   new PanelStyle("card_standard",18f,
    new PanelLayerSpec("edge","#26314C",0f),
    new PanelLayerSpec("body","#18233C",2f),
    new PanelLayerSpec("sheen","#FFFFFF10",10f)),
   new PanelStyle("card_rarity",20f,
    new PanelLayerSpec("glow","#F0B44C33",0f),
    new PanelLayerSpec("edge","#26314C",3f),
    new PanelLayerSpec("body","#18233C",6f),
    new PanelLayerSpec("sheen","#FFFFFF14",12f)),
   new PanelStyle("banner_hero",22f,
    new PanelLayerSpec("faction_wash","#57E6D41F",0f),
    new PanelLayerSpec("body","#0A0F1D",2f),
    new PanelLayerSpec("inner_glow","#FFFFFF0F",14f)),
   new PanelStyle("echo_realm",18f,
    new PanelLayerSpec("thread","#57E6D42E",0f),
    new PanelLayerSpec("body","#0D1424",3f),
    new PanelLayerSpec("veil","#9A7BFF14",9f)),
  };

  static readonly Dictionary<HeroFaction,FactionVisualToken> FactionById=factionTokens.ToDictionary(x=>x.Faction);
  static readonly Dictionary<HeroRarity,RarityVisualToken> RarityById=rarityTokens.ToDictionary(x=>x.Rarity);
  static readonly Dictionary<string,PanelStyle> StyleByKey=panelStyles.ToDictionary(x=>x.Key);

  public static IReadOnlyList<FactionVisualToken> FactionTokens{get{return factionTokens;}}
  public static IReadOnlyList<RarityVisualToken> RarityTokens{get{return rarityTokens;}}
  public static IReadOnlyList<PanelStyle> PanelStyles{get{return panelStyles;}}

  public static FactionVisualToken Faction(HeroFaction faction){
   FactionVisualToken t;
   if(!FactionById.TryGetValue(faction,out t))throw new ArgumentOutOfRangeException("faction");
   return t;
  }
  public static RarityVisualToken Rarity(HeroRarity rarity){
   RarityVisualToken t;
   if(!RarityById.TryGetValue(rarity,out t))throw new ArgumentOutOfRangeException("rarity");
   return t;
  }
  public static PanelStyle Style(string key){PanelStyle s;return StyleByKey.TryGetValue(key,out s)?s:null;}
  public static HeroPresentation Presentation(string heroId){var def=HeroCatalog.Get(heroId);return def==null?null:new HeroPresentation(def,AwakenedRealmsNarrative.ForHero(heroId));}
  public static IEnumerable<HeroPresentation> AllPresentations(){return HeroCatalog.All.Select(x=>Presentation(x.Id));}
 }
}
