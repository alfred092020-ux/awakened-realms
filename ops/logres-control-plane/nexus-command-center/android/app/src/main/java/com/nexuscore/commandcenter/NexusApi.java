package com.nexuscore.commandcenter;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Typed client for the Nexus Native Command API.
 * Bearer-token auth; SSE realtime stream with bounded backoff reconnect.
 */
final class NexusApi {
    interface SnapshotListener {
        void onSnapshot(JSONObject snapshot);
        void onStatus(String status, String detail);
    }

    private static final String PREFS = "nexus_command_center";
    private static final long BACKOFF_MIN_MS = 1500;
    private static final long BACKOFF_MAX_MS = 20000;

    private final Context app;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService io = Executors.newCachedThreadPool();
    private final AtomicBoolean streaming = new AtomicBoolean(false);
    private final AtomicLong lastSnapshotAt = new AtomicLong(0);

    NexusApi(Context ctx) {
        this.app = ctx.getApplicationContext();
    }

    private SharedPreferences prefs() {
        return app.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    String endpoint() { return prefs().getString("endpoint", ""); }
    String token() { return prefs().getString("token", ""); }
    String googleSession() { return prefs().getString("google_session", ""); }
    String googleIdentity() { return prefs().getString("google_identity", ""); }

    boolean configured() { return endpoint().startsWith("https://") || endpoint().startsWith("http://"); }

    void configure(String endpoint, String token) {
        String e = endpoint == null ? "" : endpoint.trim();
        while (e.endsWith("/")) e = e.substring(0, e.length() - 1);
        prefs().edit().putString("endpoint", e).putString("token", token == null ? "" : token.trim()).apply();
    }

    void setGoogleSession(String sessionToken, String identity) {
        prefs().edit().putString("google_session", sessionToken == null ? "" : sessionToken)
                .putString("google_identity", identity == null ? "" : identity).apply();
    }

    void clear() {
        prefs().edit().remove("endpoint").remove("token")
                .remove("google_session").remove("google_identity").apply();
    }

    long lastSnapshotAt() { return lastSnapshotAt.get(); }

    private String bearer() {
        // The configured Nexus token is the stronger credential and wins;
        // a verified Google session is used only when no token is set.
        String t = token();
        if (!t.isEmpty()) return t;
        return googleSession();
    }

    private HttpURLConnection open(String path, String method) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(endpoint() + path).openConnection();
        c.setRequestMethod(method);
        c.setConnectTimeout(8000);
        c.setReadTimeout(method.equals("GET") && path.equals("/api/events") ? 0 : 45000);
        c.setUseCaches(false);
        String b = bearer();
        if (!b.isEmpty()) c.setRequestProperty("Authorization", "Bearer " + b);
        return c;
    }

    private static String readAll(InputStream in) throws Exception {
        BufferedReader r = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8));
        StringBuilder b = new StringBuilder();
        String line;
        while ((line = r.readLine()) != null) b.append(line);
        return b.toString();
    }

    interface JsonCallback {
        void ok(JSONObject body);
        void fail(int code, String error);
    }

    void getJson(String path, JsonCallback cb) {
        io.submit(() -> {
            try {
                HttpURLConnection c = open(path, "GET");
                int rc = c.getResponseCode();
                InputStream in = rc < 400 ? c.getInputStream() : c.getErrorStream();
                JSONObject body = new JSONObject(readAll(in));
                if (rc < 300) ui.post(() -> cb.ok(body));
                else ui.post(() -> cb.fail(rc, body.optString("error", "HTTP " + rc)));
            } catch (Exception e) {
                ui.post(() -> cb.fail(-1, e.getClass().getSimpleName() + ": " + e.getMessage()));
            }
        });
    }

    void postJson(String path, JSONObject payload, JsonCallback cb) {
        io.submit(() -> {
            try {
                HttpURLConnection c = open(path, "POST");
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json");
                byte[] bytes = payload.toString().getBytes(StandardCharsets.UTF_8);
                OutputStream os = c.getOutputStream();
                os.write(bytes);
                os.close();
                int rc = c.getResponseCode();
                InputStream in = rc < 400 ? c.getInputStream() : c.getErrorStream();
                String raw = readAll(in);
                JSONObject body = raw.isEmpty() ? new JSONObject() : new JSONObject(raw);
                if (rc < 300) ui.post(() -> cb.ok(body));
                else ui.post(() -> cb.fail(rc, body.optString("message", body.optString("error", "HTTP " + rc))));
            } catch (Exception e) {
                ui.post(() -> cb.fail(-1, e.getClass().getSimpleName() + ": " + e.getMessage()));
            }
        });
    }

    /** Exchange a Google ID token for a Nexus session (server verifies with Google). */
    void googleSignInExchange(String idToken, JsonCallback cb) {
        try {
            JSONObject payload = new JSONObject().put("id_token", idToken);
            postJson("/api/session/google", payload, cb);
        } catch (Exception e) {
            cb.fail(-1, e.getMessage());
        }
    }

    /** Start (or restart) the authoritative SSE stream. */
    void startStream(SnapshotListener listener) {
        if (!streaming.compareAndSet(false, true)) return;
        io.submit(() -> {
            long backoff = BACKOFF_MIN_MS;
            while (streaming.get()) {
                HttpURLConnection c = null;
                try {
                    ui.post(() -> listener.onStatus("CONNECTING", null));
                    c = open("/api/events", "GET");
                    c.setRequestProperty("Accept", "text/event-stream");
                    int rc = c.getResponseCode();
                    if (rc != 200) throw new IllegalStateException("HTTP " + rc);
                    ui.post(() -> listener.onStatus("LIVE", null));
                    backoff = BACKOFF_MIN_MS;
                    BufferedReader r = new BufferedReader(
                        new InputStreamReader(c.getInputStream(), StandardCharsets.UTF_8));
                    String line;
                    StringBuilder data = new StringBuilder();
                    while (streaming.get() && (line = r.readLine()) != null) {
                        if (line.startsWith("data:")) {
                            data.append(line.substring(5).trim());
                        } else if (line.isEmpty() && data.length() > 0) {
                            JSONObject snap = new JSONObject(data.toString());
                            data.setLength(0);
                            lastSnapshotAt.set(System.currentTimeMillis());
                            ui.post(() -> listener.onSnapshot(snap));
                        } else if (line.isEmpty()) {
                            data.setLength(0);
                        }
                    }
                } catch (Exception e) {
                    String d = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
                    ui.post(() -> listener.onStatus("RECONNECTING", d));
                } finally {
                    if (c != null) c.disconnect();
                }
                if (!streaming.get()) break;
                try { Thread.sleep(backoff); } catch (InterruptedException ie) { break; }
                backoff = Math.min(backoff * 2, BACKOFF_MAX_MS);
            }
            ui.post(() -> listener.onStatus("OFFLINE", null));
        });
    }

    void stop() {
        streaming.set(false);
    }

    void destroy() {
        streaming.set(false);
        io.shutdownNow();
    }
}
