using System;
using IdleSlime.Core;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;
namespace IdleSlime.Runtime {
public sealed class IdleSlimeBootstrap : MonoBehaviour {
 public IdleSlimeSession Session { get; private set; } public IdleSlimeUI UI { get; private set; } float nextSave;
 [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)] static void Boot(){if(FindObjectOfType<IdleSlimeBootstrap>()!=null)return;var g=new GameObject("AwakenedRealmsRuntime");DontDestroyOnLoad(g);g.AddComponent<IdleSlimeBootstrap>();}
 void Awake(){Screen.orientation=ScreenOrientation.Portrait;Session=IdleSlimeSave.LoadOrCreate(DateTime.UtcNow);if(FindObjectOfType<EventSystem>()==null){var e=new GameObject("AwakenedRealmsEventSystem");e.AddComponent<EventSystem>();e.AddComponent<StandaloneInputModule>();DontDestroyOnLoad(e);}UI=gameObject.AddComponent<IdleSlimeUI>();UI.Initialize(Session);nextSave=Time.unscaledTime+2f;}
 void Update(){if(Time.unscaledTime>=nextSave){IdleSlimeSave.Save(Session);nextSave=Time.unscaledTime+2f;}}
 void OnApplicationPause(bool paused){if(paused)IdleSlimeSave.Save(Session);} void OnApplicationQuit(){IdleSlimeSave.Save(Session);}
}
}