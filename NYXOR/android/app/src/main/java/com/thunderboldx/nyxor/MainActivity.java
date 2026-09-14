package com.thunderboldx.nyxor;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.*;
import android.webkit.*;
import android.view.*;
import org.json.JSONObject;
import java.util.concurrent.*;
import java.io.*;

public class MainActivity extends Activity {
    private WebView web;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private static final String HOST = "appassets.androidplatform.net";
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        web = new WebView(this);
        web.setBackgroundColor(0xff0c0b10);
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setDomStorageEnabled(true);
        web.getSettings().setAllowFileAccess(false);
        web.getSettings().setAllowContentAccess(false);
        web.getSettings().setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.addJavascriptInterface(new Bridge(), "NyxorNative");
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (HOST.equals(request.getUrl().getHost())) return false;
                openTwitch(request.getUrl().toString()); return true;
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (!"https".equals(uri.getScheme()) || !HOST.equals(uri.getHost()))
                    return new WebResourceResponse("text/plain", "UTF-8", new ByteArrayInputStream(new byte[0]));
                String file = uri.getPath().equals("/") ? "index.html" : uri.getPath().substring(1);
                if (!file.matches("[a-zA-Z0-9_.-]+")) return null;
                try {
                    String type = file.endsWith(".js") ? "text/javascript" : file.endsWith(".css") ? "text/css" : "text/html";
                    return new WebResourceResponse(type, "UTF-8", getAssets().open("frontend/" + file));
                } catch (IOException error) { return new WebResourceResponse("text/plain", "UTF-8", new ByteArrayInputStream(new byte[0])); }
            }
        });
        SafeArea.attach(this, web);
        web.loadUrl("https://" + HOST + "/");
        if (Build.VERSION.SDK_INT >= 33) getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
            android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT, this::handleBack);
    }
    private void openTwitch(String address) {
        Uri uri = Uri.parse(address);
        if ("https".equals(uri.getScheme()) && ("www.twitch.tv".equals(uri.getHost()) || "twitch.tv".equals(uri.getHost())))
            runOnUiThread(() -> { try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); } catch (Exception ignored) {} });
    }
    private void uiAction(Runnable action) throws Exception {
        FutureTask<Void> task = new FutureTask<>(action, null);
        runOnUiThread(task);
        task.get(5, TimeUnit.SECONDS);
    }
    private final class Bridge {
        @JavascriptInterface public void request(String id, String payload) {
            if (!id.matches("[0-9]+")) return;
            executor.execute(() -> {
                String answer;
                try {
                    JSONObject data = new JSONObject(payload);
                    String action = data.optString("action");
                    if (action.equals("open")) { openTwitch(data.optString("url")); answer = "{\"ok\":true,\"data\":{}}"; }
                    else if (action.equals("copy_code")) {
                        JSONObject state = new JSONObject(Engine.request(MainActivity.this, "{\"action\":\"snapshot\"}")).getJSONObject("data");
                        JSONObject auth = state.getJSONObject("auth");
                        String code = auth.optString("code");
                        if (!auth.optString("status").equals("pending") || !code.matches("[A-Za-z0-9-]{4,32}")
                                || auth.optDouble("expires_at", 0) <= System.currentTimeMillis() / 1000.0)
                            throw new IllegalStateException("Код уже неактивний / Code is no longer active");
                        FutureTask<Void> copy = new FutureTask<>(() -> {
                            ClipData clip = ClipData.newPlainText("Twitch activation code", code);
                            PersistableBundle extras = new PersistableBundle();
                            extras.putBoolean("android.content.extra.IS_SENSITIVE", true);
                            clip.getDescription().setExtras(extras);
                            ClipboardManager clipboard = getSystemService(ClipboardManager.class);
                            if (clipboard == null) throw new IllegalStateException("Clipboard unavailable");
                            clipboard.setPrimaryClip(clip);
                            return null;
                        });
                        runOnUiThread(copy);
                        copy.get(5, TimeUnit.SECONDS);
                        answer = "{\"ok\":true,\"data\":{}}";
                    }
                    else if (action.equals("background_settings") || action.equals("notification_settings")) {
                        uiAction(() -> {
                            Intent settings = action.equals("notification_settings")
                                ? new Intent(android.provider.Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(android.provider.Settings.EXTRA_APP_PACKAGE, getPackageName())
                                : new Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + getPackageName()));
                            startActivity(settings);
                        });
                        answer = "{\"ok\":true,\"data\":{}}";
                    }
                    else if (action.equals("stop") || action.equals("logout")) {
                        answer = Engine.request(MainActivity.this, payload);
                        uiAction(() -> stopService(new Intent(MainActivity.this, MinerService.class)));
                    }
                    else if (action.equals("start") || action.equals("restart")) {
                        JSONObject state = new JSONObject(Engine.request(MainActivity.this, "{\"action\":\"snapshot\"}")).getJSONObject("data");
                        if (!state.optBoolean("authenticated")) throw new IllegalStateException("Спочатку підключи Twitch");
                        if (state.getJSONArray("queue").length() == 0 && state.getJSONArray("streamers").length() == 0 && state.optJSONArray("points_games").length() == 0)
                            throw new IllegalStateException("Додай гру або стрімера");
                        uiAction(() -> {
                            if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
                                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 1);
                            Intent service = new Intent(MainActivity.this, MinerService.class);
                            if (action.equals("restart")) service.setAction(MinerService.RESTART);
                            startForegroundService(service);
                        });
                        answer = "{\"ok\":true,\"data\":{\"starting\":true}}";
                    } else {
                        answer = Engine.request(MainActivity.this, payload);
                        if (action.equals("settings") && data.optJSONObject("values") != null && data.getJSONObject("values").optBoolean("launch_on_boot"))
                            uiAction(() -> {
                                if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
                                    requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 1);
                            });
                    }
                } catch (Exception error) { answer = "{\"ok\":false,\"error\":" + JSONObject.quote(error.getMessage() == null ? "NYXOR error" : error.getMessage()) + "}"; }
                final String result = answer;
                runOnUiThread(() -> { if (!isDestroyed()) web.evaluateJavascript("window.nativeReply(" + JSONObject.quote(id) + "," + result + ")", null); });
            });
        }
        @JavascriptInterface public void haptic() { runOnUiThread(() -> web.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)); }
    }
    private void handleBack() { web.evaluateJavascript("window.nyxorBack ? window.nyxorBack() : false", value -> {
        if ("false".equals(value)) moveTaskToBack(true);
    }); }
    @Override public void onBackPressed() { handleBack(); }
    @Override public void onDestroy() { web.removeJavascriptInterface("NyxorNative"); web.destroy(); executor.shutdown(); super.onDestroy(); }
}
