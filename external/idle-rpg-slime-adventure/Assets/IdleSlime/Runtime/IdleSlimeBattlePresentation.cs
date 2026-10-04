using System;
using System.Collections.Generic;
using System.Linq;
using IdleSlime.Core;

namespace IdleSlime.Runtime {
public sealed class BattleBeat {
 public string ActorName;
 public bool AllyTurn;
 public bool Skill;
 public float DamagePercent;
 public HeroFaction? Faction;
}

public sealed class BattlePresentationPlan {
 public readonly List<BattleBeat> Beats = new List<BattleBeat>();
 public readonly string EnemyName;
 public readonly int StageNumber;
 public readonly bool Victory;

 BattlePresentationPlan(string enemyName,int stageNumber,bool victory){
  EnemyName=enemyName;StageNumber=stageNumber;Victory=victory;
 }

 public static BattlePresentationPlan Build(Formation formation,IReadOnlyDictionary<string,HeroState> roster,CampaignStage stage,BattleResult result){
  var plan=new BattlePresentationPlan(EnemyNameFor(stage.Number),stage.Number,result.Victory);
  var heroes=formation.Slots
   .Select(id=>new { State=roster[id], Def=HeroCatalog.Get(id) })
   .OrderByDescending(x=>x.Def.Speed)
   .ThenBy(x=>x.Def.Name)
   .ToArray();

  float enemyRemaining=100f;
  float allyRemaining=100f;
  int enemyTurns=0;
  for(int round=0;round<2;round++){
   for(int i=0;i<heroes.Length;i++){
    var h=heroes[i];
    bool skill=((round*heroes.Length+i+1)%3)==0;
    float ratio=(float)BattleSimulator.HeroPower(h.State)/Math.Max(1,stage.EnemyPower);
    float damage=Math.Min(18f,Math.Max(5f,6f+ratio*8f+(skill?4f:0f)));
    if(result.Victory&&round==1&&i==heroes.Length-1)damage=enemyRemaining;
    damage=Math.Min(enemyRemaining,damage);
    enemyRemaining=Math.Max(0f,enemyRemaining-damage);
    plan.Beats.Add(new BattleBeat{ActorName=h.Def.Name,AllyTurn=true,Skill=skill,DamagePercent=damage,Faction=h.Def.Faction});
    if(enemyRemaining<=0f)break;

    if(i%2==1){
     enemyTurns++;
     float pressure=(float)stage.EnemyPower/Math.Max(1,result.TeamPower);
     float retaliation=Math.Min(24f,Math.Max(5f,7f+pressure*6f+(enemyTurns%3==0?4f:0f)));
     if(!result.Victory&&round==1&&i>=3)retaliation=allyRemaining;
     retaliation=Math.Min(allyRemaining,retaliation);
     allyRemaining=Math.Max(0f,allyRemaining-retaliation);
     plan.Beats.Add(new BattleBeat{ActorName=plan.EnemyName,AllyTurn=false,Skill=enemyTurns%3==0,DamagePercent=retaliation,Faction=null});
     if(allyRemaining<=0f)break;
    }
   }
   if(enemyRemaining<=0f||allyRemaining<=0f)break;
  }

  if(result.Victory&&enemyRemaining>0f){
   var finisher=heroes[0];
   plan.Beats.Add(new BattleBeat{ActorName=finisher.Def.Name,AllyTurn=true,Skill=true,DamagePercent=enemyRemaining,Faction=finisher.Def.Faction});
  }else if(!result.Victory&&allyRemaining>0f){
   plan.Beats.Add(new BattleBeat{ActorName=plan.EnemyName,AllyTurn=false,Skill=true,DamagePercent=allyRemaining,Faction=null});
  }
  return plan;
 }

 static string EnemyNameFor(int stage){
  int tier=(stage-1)/5;
  string[] names={"Ashfang Pack","Tidebound Warden","Verdant Colossus","Eclipse Sovereign"};
  return names[Math.Max(0,Math.Min(names.Length-1,tier))];
 }
}
}
