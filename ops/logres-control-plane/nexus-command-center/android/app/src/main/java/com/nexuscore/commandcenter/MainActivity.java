package com.nexuscore.commandcenter;

import android.annotation.SuppressLint;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.SslErrorHandler;
import android.net.http.SslError;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.ComponentActivity;
import androidx.activity.OnBackPressedCallback;

public final class MainActivity extends ComponentActivity {
    private static final String PREFS = "nexus_command_center";
    private static final String KEY_URL = "base_url";

    private FrameLayout root;
    private WebView webView;
    private String configuredUrl;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.rgb(7, 7, 9));
        getWindow().setNavigationBarColor(Color.rgb(7, 7, 9));

        root = new FrameLayout(this);
        root.setBackgroundColor(Color.rgb(7, 7, 9));
        setContentView(root);

        configuredUrl = getPreferences(MODE_PRIVATE).getString(KEY_URL, "");
        if (state != null && state.getBoolean("web_visible", false) && isValidHttps(configuredUrl)) {
            showWebView(false);
        } else if (isValidHttps(configuredUrl)) {
            showWebView(true);
        } else {
            showSetup();
        }

        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (webView != null && webView.canGoBack()) {
                    webView.goBack();
                } else {
                    setEnabled(false);
                    getOnBackPressedDispatcher().onBackPressed();
                    setEnabled(true);
                }
            }
        });
    }

    private void showSetup() {
        root.removeAllViews();

        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(28), dp(40), dp(28), dp(28));
        panel.setGravity(Gravity.CENTER_VERTICAL);
        panel.setBackgroundColor(Color.rgb(7, 7, 9));

        TextView eyebrow = text("NEXUS CORE INC", 12, Color.rgb(139, 92, 246));
        TextView title = text("Command Center", 30, Color.WHITE);
        TextView copy = text(
            "Enter the HTTPS address of your private Nexus Command Center. The app stores only the server address. Your access token remains inside the Command Center's HttpOnly session.",
            15, Color.rgb(185, 185, 195)
        );

        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setHint("https://command.example.com");
        input.setText(configuredUrl);
        input.setTextColor(Color.WHITE);
        input.setHintTextColor(Color.rgb(110, 110, 120));
        input.setBackgroundColor(Color.rgb(24, 24, 30));
        input.setPadding(dp(14), dp(14), dp(14), dp(14));

        Button connect = new Button(this);
        connect.setText("Connect securely");
        connect.setAllCaps(false);
        connect.setOnClickListener(v -> {
            String value = normalize(input.getText().toString());
            if (!isValidHttps(value)) {
                Toast.makeText(this, "Use a valid https:// address.", Toast.LENGTH_LONG).show();
                return;
            }
            configuredUrl = value;
            getPreferences(MODE_PRIVATE).edit().putString(KEY_URL, value).apply();
            showWebView(true);
        });

        panel.addView(eyebrow, lpMatchWrap(0));
        panel.addView(title, lpMatchWrap(8));
        panel.addView(copy, lpMatchWrap(14));
        panel.addView(input, lpMatchWrap(22));
        panel.addView(connect, lpMatchWrap(14));

        root.addView(panel, new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ));
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void showWebView(boolean load) {
        root.removeAllViews();

        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(7, 7, 9));
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(false);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setSupportMultipleWindows(false);

        CookieManager cookies = CookieManager.getInstance();
        cookies.setAcceptCookie(true);
        cookies.setAcceptThirdPartyCookies(webView, false);

        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri target = request.getUrl();
                if ("https".equalsIgnoreCase(target.getScheme()) && sameHost(target, Uri.parse(configuredUrl))) {
                    return false;
                }
                if ("https".equalsIgnoreCase(target.getScheme())) {
                    startActivity(new Intent(Intent.ACTION_VIEW, target));
                }
                return true;
            }

            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                handler.cancel();
                Toast.makeText(MainActivity.this, "TLS validation failed.", Toast.LENGTH_LONG).show();
            }
        });

        webView.setOnLongClickListener(v -> {
            showServerMenu();
            return true;
        });

        root.addView(webView, new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ));

        if (load) {
            webView.loadUrl(configuredUrl);
        }
    }

    private void showServerMenu() {
        new AlertDialog.Builder(this)
            .setTitle("Nexus Command Center")
            .setMessage("Server: " + configuredUrl + "\n\nChange the server only if your private Command Center address changes.")
            .setPositiveButton("Reload", (d, w) -> webView.reload())
            .setNeutralButton("Change server", (d, w) -> showSetup())
            .setNegativeButton("Cancel", null)
            .show();
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        out.putBoolean("web_visible", webView != null);
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }

    private static String normalize(String raw) {
        String value = raw == null ? "" : raw.trim();
        while (value.endsWith("/")) value = value.substring(0, value.length() - 1);
        return value;
    }

    private static boolean isValidHttps(String value) {
        try {
            Uri uri = Uri.parse(value);
            return "https".equalsIgnoreCase(uri.getScheme())
                && uri.getHost() != null
                && !uri.getHost().trim().isEmpty();
        } catch (RuntimeException ignored) {
            return false;
        }
    }

    private static boolean sameHost(Uri a, Uri b) {
        return a.getHost() != null && b.getHost() != null
            && a.getHost().equalsIgnoreCase(b.getHost())
            && effectivePort(a) == effectivePort(b);
    }

    private static int effectivePort(Uri uri) {
        return uri.getPort() == -1 ? 443 : uri.getPort();
    }

    private TextView text(String value, int sp, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        view.setTextColor(color);
        return view;
    }

    private LinearLayout.LayoutParams lpMatchWrap(int topMarginDp) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        );
        lp.topMargin = dp(topMarginDp);
        return lp;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
