package com.thunderboldx.nyxor;

import android.content.Context;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import java.io.*;
import org.json.JSONObject;

final class Engine {
    private static boolean initialized;
    static synchronized void initialize(Context context) throws IOException {
        if (initialized) return;
        File root = new File(context.getFilesDir(), "nyxor");
        File locales = new File(root, "locales");
        if (!locales.isDirectory() && !locales.mkdirs()) throw new IOException("Cannot create app storage");
        for (String locale : new String[]{"uk.json", "en.json"}) {
            try (InputStream input = context.getAssets().open("locales/" + locale);
                 OutputStream output = new FileOutputStream(new File(locales, locale))) {
                byte[] buffer = new byte[8192]; int size;
                while ((size = input.read(buffer)) != -1) output.write(buffer, 0, size);
            }
        }
        if (!Python.isStarted()) Python.start(new AndroidPlatform(context.getApplicationContext()));
        Python.getInstance().getModule("nyxor.android_runtime").callAttr("initialize", root.getAbsolutePath(), new NetworkSupport(context));
        initialized = true;
    }
    static String request(Context context, String payload) throws IOException {
        try {
            String action = new JSONObject(payload).optString("action");
            if (action.equals("stop") || action.equals("logout")) BackgroundPreferences.setWanted(context, false);
        } catch (org.json.JSONException ignored) {}
        String response = requestRuntime(context, payload);
        try {
            JSONObject result = new JSONObject(response);
            JSONObject data = result.optJSONObject("data");
            if (result.optBoolean("ok") && data != null && data.optJSONObject("settings") != null)
                BackgroundPreferences.sync(context, data.getJSONObject("settings"));
        } catch (org.json.JSONException ignored) {}
        return response;
    }
    static String requestRuntime(Context context, String payload) throws IOException {
        initialize(context);
        return Python.getInstance().getModule("nyxor.android_runtime").callAttr("request", payload).toString();
    }
}
