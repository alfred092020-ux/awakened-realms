package com.nexuscore.awakenedrealms;

import android.os.Bundle;
import android.webkit.WebSettings;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        if (bridge != null && bridge.getWebView() != null) {
            bridge.getWebView().getSettings().setCacheMode(WebSettings.LOAD_NO_CACHE);
            bridge.getWebView().clearCache(true);
            bridge.getWebView().clearHistory();
            bridge.getWebView().reload();
        }
    }
}
