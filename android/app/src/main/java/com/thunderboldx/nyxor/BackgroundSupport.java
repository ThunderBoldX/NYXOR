package com.thunderboldx.nyxor;

import android.app.ActivityManager;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.PowerManager;
import android.provider.Settings;
import org.json.JSONObject;
import org.json.JSONException;

final class BackgroundSupport {
    static JSONObject status(Context context) throws JSONException {
        PowerManager power = context.getSystemService(PowerManager.class);
        ActivityManager activity = context.getSystemService(ActivityManager.class);
        return new JSONObject()
            .put("battery_optimized", !power.isIgnoringBatteryOptimizations(context.getPackageName()))
            .put("power_save", power.isPowerSaveMode())
            .put("device_idle", power.isDeviceIdleMode())
            .put("background_restricted", Build.VERSION.SDK_INT >= 28 && activity.isBackgroundRestricted());
    }
    // Called only after the user taps Allow background farming in Settings.
    static Intent permissionIntent(Context context) {
        PowerManager power = context.getSystemService(PowerManager.class);
        if (power.isIgnoringBatteryOptimizations(context.getPackageName())) return appSettings(context);
        return new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
            Uri.parse("package:" + context.getPackageName()));
    }
    static Intent appSettings(Context context) {
        return new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
            Uri.parse("package:" + context.getPackageName()));
    }
}
