package fr.jeuxrpg.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Build;
import android.window.OnBackInvokedDispatcher;
import android.webkit.ConsoleMessage;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.webkit.WebViewAssetLoader;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final String ORIGIN="https://appassets.androidplatform.net";
    private WebView web;
    private JSONObject manifest;
    private String server;
    private final ExecutorService network=Executors.newFixedThreadPool(4);
    private final Set<String> assets=new HashSet<>();

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        try {
            try(InputStream stream=getAssets().open("web/manifest.json")){manifest=new JSONObject(readText(stream));}
            server=manifest.getString("server");
            URI origin=URI.create(server);
            if(!"https".equals(origin.getScheme())||origin.getHost()==null||origin.getUserInfo()!=null||!server.equals("https://"+origin.getHost()))throw new IllegalArgumentException("Serveur invalide");
            Iterator<String> keys=manifest.getJSONObject("web_assets").keys();
            while(keys.hasNext())assets.add(keys.next());
            Collections.addAll(assets,"index.html","mobile_bridge.js","manifest.json","classes.json","solo-engine.zip");
            for(String file:new String[]{"pyodide.mjs","pyodide.mjs.map","pyodide.asm.mjs","pyodide.asm.wasm","pyodide-lock.json","python_stdlib.zip"})assets.add("vendor/pyodide/"+file);
            web=new WebView(this);web.setBackgroundColor(Color.rgb(16,24,32));setContentView(web);
            web.setOnApplyWindowInsetsListener((view,insets)->{view.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;});
            WebSettings settings=web.getSettings();
            settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);
            settings.setAllowFileAccess(false);settings.setAllowContentAccess(false);
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
            settings.setSupportMultipleWindows(false);settings.setMediaPlaybackRequiresUserGesture(true);
            WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
            WebViewAssetLoader loader=new WebViewAssetLoader.Builder().addPathHandler("/",this::localAsset).build();
            web.setWebViewClient(new WebViewClient(){
                @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){
                    if(!"https".equals(request.getUrl().getScheme())||!"appassets.androidplatform.net".equals(request.getUrl().getHost()))return errorResponse(403,"Ressource externe refusée.");
                    WebResourceResponse result=loader.shouldInterceptRequest(request.getUrl());
                    return result!=null?result:errorResponse(404,"Ressource introuvable.");
                }
                @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return !request.getUrl().toString().equals(ORIGIN+"/");}
            });
            web.setWebChromeClient(new WebChromeClient(){
                @Override public void onPermissionRequest(PermissionRequest request){request.deny();}
                @Override public boolean onConsoleMessage(ConsoleMessage message){if(BuildConfig.DEBUG)android.util.Log.d("JeuxRPG",message.message());return true;}
            });
            if(!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER))throw new IllegalStateException("Mettez à jour Android System WebView pour lancer le jeu.");
            WebViewCompat.addWebMessageListener(web,"rpgNativeApi",Collections.singleton(ORIGIN),(view,message,source,isMain,reply)->{
                if(!isMain||!"https".equals(source.getScheme())||!"appassets.androidplatform.net".equals(source.getHost()))return;
                try {
                    JSONObject input=new JSONObject(message.getData());
                    if("finish".equals(input.optString("type"))){finish();return;}
                    network.execute(()->{
                        JSONObject output=online(input);
                        runOnUiThread(()->{if(!isFinishing())reply.postMessage(output.toString());});
                    });
                } catch(Exception ignored) { }
            });
            web.loadUrl(ORIGIN+"/");
            if(Build.VERSION.SDK_INT>=33)getOnBackInvokedDispatcher().registerOnBackInvokedCallback(OnBackInvokedDispatcher.PRIORITY_DEFAULT,this::handleBack);
        } catch(Exception error){new AlertDialog.Builder(this).setTitle("Jeux RPG").setMessage(error.getMessage()).setPositiveButton("Fermer",(dialog,button)->finish()).show();}
    }

    private WebResourceResponse localAsset(String path) {
        String name=path.isEmpty()?"index.html":path;
        if(name.equals("api/classes"))name="classes.json";
        if(!assets.contains(name))return errorResponse(404,"Ressource introuvable.");
        try {
            String type=name.endsWith(".html")?"text/html":name.endsWith(".js")||name.endsWith(".mjs")?"text/javascript":name.endsWith(".css")?"text/css":name.endsWith(".json")||name.endsWith(".map")?"application/json":name.endsWith(".wasm")?"application/wasm":name.endsWith(".zip")?"application/zip":"application/octet-stream";
            Map<String,String> headers=new HashMap<>();headers.put("Cache-Control","no-store");headers.put("X-Content-Type-Options","nosniff");
            headers.put("Content-Security-Policy",name.equals("solo_worker.js")?manifest.getString("worker_csp"):"default-src 'none'; script-src 'self'; worker-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'");
            return new WebResourceResponse(type,type.startsWith("text/")||type.equals("application/json")?"UTF-8":null,200,"OK",headers,getAssets().open("web/"+name));
        } catch(Exception error){return errorResponse(503,"Ressource locale indisponible.");}
    }

    private WebResourceResponse errorResponse(int status,String message){
        return new WebResourceResponse("application/json","UTF-8",status,"Error",Collections.singletonMap("Cache-Control","no-store"),new ByteArrayInputStream(("{\"error\":\"unavailable\",\"message\":\""+message+"\"}").getBytes(StandardCharsets.UTF_8)));
    }

    private JSONObject online(JSONObject input){
        JSONObject output=new JSONObject();HttpURLConnection connection=null;
        try {
            output.put("id",input.getInt("id"));
            String path=input.getString("path"),method=input.getString("method"),body=input.optString("body","");
            if(!path.startsWith("/api/")||path.contains("..")||path.contains("\\")||path.contains("#")||(!method.equals("GET")&&!method.equals("POST"))||body.getBytes(StandardCharsets.UTF_8).length>65536)throw new IllegalArgumentException();
            URL url=new URL(server+path);connection=(HttpURLConnection)url.openConnection();
            connection.setConnectTimeout(20000);connection.setReadTimeout(30000);connection.setInstanceFollowRedirects(false);connection.setRequestMethod(method);connection.setRequestProperty("Origin",server);
            JSONObject headers=input.optJSONObject("headers");
            if(headers!=null)for(String key:new String[]{"authorization","content-type","accept","x-rpg-chat-connection","x-rpg-command-ack","x-rpg-bundles","x-rpg-bundle-hashes"})if(headers.has(key))connection.setRequestProperty(key,headers.getString(key));
            if(method.equals("POST")){connection.setDoOutput(true);connection.getOutputStream().write(body.getBytes(StandardCharsets.UTF_8));}
            int status=connection.getResponseCode();
            InputStream stream=status>=400?connection.getErrorStream():connection.getInputStream();
            String response=stream==null?"{}":readText(stream);
            if(stream!=null)stream.close();
            output.put("status",status);output.put("body",response);output.put("headers",new JSONObject().put("content-type","application/json"));
        } catch(Exception error){
            try{output.put("status",503);output.put("body","{\"error\":\"unavailable\",\"message\":\"Serveur en ligne inaccessible. Le solo reste disponible sur cet appareil.\"}");output.put("headers",new JSONObject().put("content-type","application/json"));}catch(Exception ignored){}
        } finally{if(connection!=null)connection.disconnect();}
        return output;
    }

    private static String readText(InputStream stream)throws java.io.IOException{
        ByteArrayOutputStream buffer=new ByteArrayOutputStream();byte[] chunk=new byte[8192];int count;
        while((count=stream.read(chunk))!=-1)buffer.write(chunk,0,count);
        return new String(buffer.toByteArray(),StandardCharsets.UTF_8);
    }

    @Override protected void onPause(){if(web!=null)web.evaluateJavascript("globalThis.rpgMobile?.flush().catch(()=>{})",null);super.onPause();}
    private void handleBack(){if(web!=null)web.evaluateJavascript("globalThis.rpgMobile?.exit()",null);else finish();}
    @Override public void onBackPressed(){handleBack();}
    @Override protected void onDestroy(){network.shutdownNow();if(web!=null)web.destroy();super.onDestroy();}
}
