package com.thunderboldx.nyxor;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import java.net.InetAddress;
import java.net.UnknownHostException;

/** Called only by the embedded Python runtime, never exposed to WebView. */
public final class NetworkSupport {
    private final ConnectivityManager connectivity;

    public NetworkSupport(Context context) {
        connectivity = context.getApplicationContext().getSystemService(ConnectivityManager.class);
    }

    public String[] resolve(String host) throws UnknownHostException {
        InetAddress[] addresses = InetAddress.getAllByName(host);
        String[] result = new String[addresses.length];
        for (int i = 0; i < addresses.length; i++) result[i] = addresses[i].getHostAddress();
        return result;
    }

    public String status() {
        if (connectivity == null) return "unknown";
        Network active = connectivity.getActiveNetwork();
        if (active == null) return "offline";
        NetworkCapabilities caps = connectivity.getNetworkCapabilities(active);
        if (caps == null) return "unknown";
        if (caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_CAPTIVE_PORTAL)) return "captive";
        if (!caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)) return "no_internet";
        return "available";
    }
}
