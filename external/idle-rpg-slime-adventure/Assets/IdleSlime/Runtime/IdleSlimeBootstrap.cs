using System;
using IdleSlime.Core;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace IdleSlime.Runtime {
public sealed class IdleSlimeBootstrap : MonoBehaviour {
 public IdleSlimeSession Session { get; private set; }
 public IdleSlimeUI UI { get; private set; }
 [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)] static void Boot(){if(FindObjectOfType<IdleSlimeBootstrap>()!=null)return;var g=new GameObject("IdleSlimeRuntime");DontDestroyOnLoad(g);g.AddComponent<IdleSlimeBootstrap>();}
 void Awake(){Screen.orientation=ScreenOrientation.Portrait;Session=new IdleSlimeSession(DateTime.UtcNow);if(FindObjectOfType<EventSystem>()==null){var e=new GameObject("IdleSlimeEventSystem");e.AddComponent<EventSystem>();e.AddComponent<StandaloneInputModule>();DontDestroyOnLoad(e);}UI=gameObject.AddComponent<IdleSlimeUI>();UI.Initialize(Session);}
}
}
