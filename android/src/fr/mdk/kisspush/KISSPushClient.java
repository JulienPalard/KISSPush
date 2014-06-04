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

	private static final String BASE_URL = "http://mdk.fr:8080/";

	private AsyncHttpClient client = new AsyncHttpClient();
	private String reg_id = "";

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
		client.get(getAbsoluteUrl(url), params, responseHandler);
	}

	public void post(String url, RequestParams params,
			AsyncHttpResponseHandler responseHandler) {
		client.post(getAbsoluteUrl(url), params, responseHandler);
	}

	private String getAbsoluteUrl(String relativeUrl) {
		return BASE_URL + relativeUrl;
	}

	public void get_alias(final Callback<ArrayList<String>> callback)
    {
	    get("alias", new RequestParams("reg_id", reg_id),
				new JsonHttpResponseHandler() {
					@Override
					public void onSuccess(JSONArray response) {
						ArrayList<String> aliases = new ArrayList<String>();
						try {
							for (int i = 0; i < response.length(); i++) {

								aliases.add(response.getString(i));
								//mDisplay.append(" -> " + alias + "\n");
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
		post("register", new RequestParams("reg_id", reg_id),
				new AsyncHttpResponseHandler() {
					@Override
					public void onSuccess(String response) {
						Log.i(TAG, "Registration sent.");
					}
				});
	}
}