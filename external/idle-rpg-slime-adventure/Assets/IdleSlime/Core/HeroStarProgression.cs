using System;
using System.Collections.Generic;

namespace IdleSlime.Core {
[Serializable]
public sealed class StarUpRequirement {
 public HeroRarity Rarity;
 public int FromStars;
 public int ToStars;
 public int SameHeroCopies;
 public HeroRarity FodderRarity;
 public int FodderStars;
 public int FodderCount;
 public bool SameFactionFodder;

 public StarUpRequirement(HeroRarity rarity,int fromStars,int sameCopies,HeroRarity fodderRarity,int fodderStars,int fodderCount,bool sameFaction){
  Rarity=rarity;
  FromStars=fromStars;
  ToStars=fromStars+1;
  SameHeroCopies=sameCopies;
  FodderRarity=fodderRarity;
  FodderStars=fodderStars;
  FodderCount=fodderCount;
  SameFactionFodder=sameFaction;
 }
}

public static class StarRules {
 static readonly Dictionary<HeroRarity,int> MaxByRarity=new Dictionary<HeroRarity,int>{
  {HeroRarity.Rare,5},
  {HeroRarity.Epic,8},
  {HeroRarity.Legendary,11},
  {HeroRarity.Mythic,15}
 };

 static readonly StarUpRequirement[] Requirements={
  new StarUpRequirement(HeroRarity.Rare,3,1,HeroRarity.Rare,3,2,false),
  new StarUpRequirement(HeroRarity.Rare,4,1,HeroRarity.Rare,4,1,false),

  new StarUpRequirement(HeroRarity.Epic,4,1,HeroRarity.Rare,4,2,false),
  new StarUpRequirement(HeroRarity.Epic,5,1,HeroRarity.Epic,4,1,false),
  new StarUpRequirement(HeroRarity.Epic,6,1,HeroRarity.Epic,5,2,false),
  new StarUpRequirement(HeroRarity.Epic,7,1,HeroRarity.Epic,6,1,false),

  new StarUpRequirement(HeroRarity.Legendary,5,1,HeroRarity.Epic,5,2,false),
  new StarUpRequirement(HeroRarity.Legendary,6,1,HeroRarity.Epic,6,1,false),
  new StarUpRequirement(HeroRarity.Legendary,7,1,HeroRarity.Legendary,6,1,true),
  new StarUpRequirement(HeroRarity.Legendary,8,1,HeroRarity.Epic,7,2,false),
  new StarUpRequirement(HeroRarity.Legendary,9,2,HeroRarity.Legendary,7,1,true),
  new StarUpRequirement(HeroRarity.Legendary,10,2,HeroRarity.Legendary,8,1,true),

  new StarUpRequirement(HeroRarity.Mythic,6,1,HeroRarity.Legendary,5,2,true),
  new StarUpRequirement(HeroRarity.Mythic,7,1,HeroRarity.Legendary,6,1,true),
  new StarUpRequirement(HeroRarity.Mythic,8,1,HeroRarity.Legendary,6,2,true),
  new StarUpRequirement(HeroRarity.Mythic,9,1,HeroRarity.Legendary,7,1,true),
  new StarUpRequirement(HeroRarity.Mythic,10,2,HeroRarity.Legendary,8,1,true),
  new StarUpRequirement(HeroRarity.Mythic,11,2,HeroRarity.Legendary,8,2,true),
  new StarUpRequirement(HeroRarity.Mythic,12,2,HeroRarity.Legendary,9,1,true),
  new StarUpRequirement(HeroRarity.Mythic,13,2,HeroRarity.Legendary,9,2,true),
  new StarUpRequirement(HeroRarity.Mythic,14,3,HeroRarity.Legendary,10,1,true)
 };

 public static int StartingStars(HeroRarity rarity){return (int)rarity;}
 public static int MaxStars(HeroRarity rarity){int value;return MaxByRarity.TryGetValue(rarity,out value)?value:StartingStars(rarity);}
 public static bool IsMaxed(HeroRarity rarity,int stars){return stars>=MaxStars(rarity);}

 public static StarUpRequirement Requirement(HeroRarity rarity,int currentStars){
  for(int i=0;i<Requirements.Length;i++)if(Requirements[i].Rarity==rarity&&Requirements[i].FromStars==currentStars)return Requirements[i];
  return null;
 }

 public static int VisualEvolutionStage(HeroRarity rarity,int stars){
  if(rarity==HeroRarity.Legendary){
   if(stars>=11)return 2;
   if(stars>=8)return 1;
   return 0;
  }
  if(rarity==HeroRarity.Mythic){
   if(stars>=15)return 4;
   if(stars>=13)return 3;
   if(stars>=11)return 2;
   if(stars>=8)return 1;
   return 0;
  }
  return 0;
 }

 public static string VisualAssetSuffix(HeroRarity rarity,int stars){
  int stage=VisualEvolutionStage(rarity,stars);
  return stage<=0?"base":"evo"+stage;
 }

 public static int ClampStars(HeroRarity rarity,int stars){
  return Math.Max(StartingStars(rarity),Math.Min(MaxStars(rarity),stars));
 }

 public static string FodderKey(HeroFaction faction,HeroRarity rarity,int stars){
  return faction+"|"+rarity+"|"+stars;
 }
}
}
