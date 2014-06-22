package fr.mdk.kisspush;

import java.util.ArrayList;

import org.json.JSONArray;
import org.json.JSONException;

import android.util.Log;

import com.loopj.android.http.AsyncHttpClient;
import com.loopj.android.http.AsyncHttpResponseHandler;
import com.loopj.android.http.JsonHttpResponseHandler;
import com.loopj.android.http.RequestParams;

public class KISSPushClient {
	/**
	 * Tag used on log messages.
	 */
	static final String TAG = "KISSPush";

	private static final String BASE_URL = "http://api.kisspush.net/";

	private AsyncHttpClient client = new AsyncHttpClient();
	private String reg_id = "null";

	public interface Callback<T> {
		   public void callback(T t);
		}

	public KISSPushClient()
	{
	}

	public void set_reg_id(String reg_id)
	{
		this.reg_id = reg_id;
	}

	public void get(String url, RequestParams params,
			AsyncHttpResponseHandler responseHandler) {
		if (params == null)
			client.get(getAbsoluteUrl(url), responseHandler);
		else
			client.get(getAbsoluteUrl(url), params, responseHandler);
	}

	public void post(String url, RequestParams params,
			AsyncHttpResponseHandler responseHandler) {
		if (params == null)
			client.post(getAbsoluteUrl(url), responseHandler);
		else
			client.post(getAbsoluteUrl(url), params, responseHandler);
	}

	public void put(String url, RequestParams params,
			AsyncHttpResponseHandler responseHandler) {
		if (params == null)
			client.put(getAbsoluteUrl(url), responseHandler);
		else
			client.put(getAbsoluteUrl(url), params, responseHandler);
	}

	public void delete(String url, RequestParams params,
			AsyncHttpResponseHandler responseHandler) {
		if (params == null)
			client.delete(null, getAbsoluteUrl(url), responseHandler);
		else
			client.delete(null, getAbsoluteUrl(url), null, params, responseHandler);
	}

	public void add_alias(String alias, JsonHttpResponseHandler responseHandler)
	{
		this.put("user/" + reg_id + "/subscription/" + alias, null, responseHandler);
	}

	public void delete_alias(String alias, JsonHttpResponseHandler responseHandler)
	{
		this.delete("user/" + reg_id + "/subscription/" + alias , null, responseHandler);
	}

	private String getAbsoluteUrl(String relativeUrl) {
		return BASE_URL + relativeUrl;
	}

	public void list_channel(String channel, final Callback<ArrayList<String>> callback)
	{
		get("channel/" + channel, null,
					new	JsonHttpResponseHandler(){
			@Override
			public void onSuccess(JSONArray response) {
				ArrayList<String> messages = new ArrayList<String>();
				try {
					for (int i = 0; i < response.length(); i++) {

						messages.add(response.getJSONObject(i).getString("message"));
						;
					}
					callback.callback(messages);
				} catch (JSONException e) {
					Log.e(TAG, "Can't parse /channel/ response");
				}
			}
		}
		);
	}

	public void get_alias(final Callback<ArrayList<String>> callback)
    {
	    get("user/" + reg_id + "/subscription/", null,
				new JsonHttpResponseHandler() {
					@Override
					public void onSuccess(JSONArray response) {
						ArrayList<String> aliases = new ArrayList<String>();
						try {
							for (int i = 0; i < response.length(); i++) {

								aliases.add(response.getString(i));
								;
							}
							callback.callback(aliases);
						} catch (JSONException e) {
							Log.e(TAG, "Can't parse /alias response");
						}
					}
				});
    }

	public void register() {
		put("user/" + reg_id, null,
				new AsyncHttpResponseHandler() {
					@Override
					public void onSuccess(String response) {
						Log.i(TAG, "Registration sent.");
					}
				});
	}
}