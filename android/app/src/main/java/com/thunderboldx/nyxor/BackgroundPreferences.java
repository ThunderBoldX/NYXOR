package com.thunderboldx.nyxor;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONObject;

final class BackgroundPreferences {
    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences("nyxor-background", Context.MODE_PRIVATE);
    }
    static boolean bootEnabled(Context context) { return prefs(context).getBoolean("launch_on_boot", false); }
    static boolean wanted(Context context) { return prefs(context).getBoolean("wanted", false); }
    static void setWanted(Context context, boolean value) {
        prefs(context).edit().putBoolean("wanted", value).commit();
    }
    static boolean english(Context context) { return "en".equals(prefs(context).getString("language", "uk")); }
    static void sync(Context context, JSONObject settings) {
        prefs(context).edit().putBoolean("launch_on_boot", settings.optBoolean("launch_on_boot", false))
            .putString("language", settings.optString("language", "uk")).apply();
    }
}
