package com.nexuscore.commandcenter;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.provider.Settings;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Shared visual language for the Nexus Command Center native app. */
final class NexusTheme {
    static final int BG = Color.rgb(7, 7, 10);
    static final int SURFACE = Color.rgb(15, 15, 21);
    static final int CARD = Color.rgb(20, 20, 28);
    static final int CARD_HI = Color.rgb(28, 28, 38);
    static final int LINE = Color.rgb(44, 44, 56);
    static final int TEXT = Color.rgb(244, 244, 250);
    static final int MUTED = Color.rgb(158, 158, 176);
    static final int FAINT = Color.rgb(112, 112, 130);
    static final int PURPLE = Color.rgb(139, 92, 246);
    static final int CYAN = Color.rgb(94, 231, 196);
    static final int GREEN = Color.rgb(52, 211, 153);
    static final int AMBER = Color.rgb(251, 191, 36);
    static final int RED = Color.rgb(248, 113, 113);
    static final int BLUE = Color.rgb(96, 165, 250);
    static final int ORANGE = Color.rgb(251, 146, 60);

    private NexusTheme() {}

    static int dp(Context c, float v) {
        return Math.round(v * c.getResources().getDisplayMetrics().density);
    }

    static int stateColor(String state) {
        if (state == null) return MUTED;
        switch (state) {
            case "AUTONOMOUS": return GREEN;
            case "VERIFYING": return CYAN;
            case "APPROVAL_REQUIRED": return AMBER;
            case "BLOCKED": return ORANGE;
            case "FAILED": return RED;
            case "DONE": return BLUE;
            case "READY": return PURPLE;
            case "OFFLINE": return RED;
            case "IDLE": return MUTED;
            case "OK": return GREEN;
            case "STALE": return AMBER;
            case "ERROR": return RED;
            default: return MUTED;
        }
    }

    static GradientDrawable cardBg(int color, float radiusDp, Context c) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(color);
        g.setCornerRadius(dp(c, radiusDp));
        g.setStroke(dp(c, 1), LINE);
        return g;
    }

    static GradientDrawable pillBg(int color, Context c) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(withAlpha(color, 40));
        g.setCornerRadius(dp(c, 999));
        g.setStroke(dp(c, 1), withAlpha(color, 160));
        return g;
    }

    static int withAlpha(int color, int alpha) {
        return Color.argb(alpha, Color.red(color), Color.green(color), Color.blue(color));
    }

    static TextView label(Context c, String s, float sp, int color) {
        TextView v = new TextView(c);
        v.setText(s);
        v.setTextSize(sp);
        v.setTextColor(color);
        v.setLineSpacing(0, 1.12f);
        return v;
    }

    static TextView section(Context c, String s) {
        TextView v = label(c, s.toUpperCase(java.util.Locale.US), 11, FAINT);
        v.setTypeface(Typeface.DEFAULT_BOLD);
        v.setLetterSpacing(0.09f);
        v.setPadding(0, dp(c, 18), 0, dp(c, 8));
        return v;
    }

    static LinearLayout column(Context c, int padDp) {
        LinearLayout x = new LinearLayout(c);
        x.setOrientation(LinearLayout.VERTICAL);
        x.setPadding(dp(c, padDp), dp(c, padDp), dp(c, padDp), dp(c, padDp));
        return x;
    }

    static LinearLayout.LayoutParams lp(int topDp, Context c) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        p.topMargin = dp(c, topDp);
        return p;
    }

    static String fmtElapsed(long ms) {
        if (ms < 0) return "—";
        long s = ms / 1000;
        if (s < 60) return s + "s";
        if (s < 3600) return (s / 60) + "m " + (s % 60) + "s";
        if (s < 86400) return (s / 3600) + "h " + ((s % 3600) / 60) + "m";
        return (s / 86400) + "d " + ((s % 86400) / 3600) + "h";
    }

    static boolean reducedMotion(Context c) {
        try {
            float scale = Settings.Global.getFloat(c.getContentResolver(),
                Settings.Global.ANIMATOR_DURATION_SCALE, 1f);
            return scale == 0f;
        } catch (Exception e) {
            return false;
        }
    }
}
