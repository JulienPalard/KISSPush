package fr.mdk.kisspush;

import java.util.ArrayList;

import android.support.v7.app.ActionBarActivity;
import android.support.v7.app.ActionBar;
import android.support.v4.app.Fragment;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.ListView;
import android.os.Build;

public class Channel extends ActionBarActivity {
	
	private KISSPushClient kiss_push_cli = new KISSPushClient();
	private Context context;
	private ListView listViewChannels;
	private Bundle savedInstanceState;
	
	@Override
	protected void onCreate(Bundle savedInstanceState) {
		super.onCreate(savedInstanceState);
		setContentView(R.layout.activity_channel);
		context = getApplicationContext();
		listViewChannels = (ListView) findViewById(R.id.listViewChannels);
		
		Intent intent = getIntent();
		String channel = intent.getStringExtra(KISSPush.MESSAGE_CHANNEL_NAME);
		kiss_push_cli
		.list_channel(channel, new KISSPushClient.Callback<ArrayList<String>>() {

			@Override
			public void callback(ArrayList<String> t) {
				ArrayAdapter<String> adapter = new ArrayAdapter<String>(
						context, android.R.layout.simple_list_item_1, t);
				if (listViewChannels != null)
					listViewChannels.setAdapter(adapter);
			}
		});
	}

	@Override
	public boolean onCreateOptionsMenu(Menu menu) {

		// Inflate the menu; this adds items to the action bar if it is present.
		getMenuInflater().inflate(R.menu.channel, menu);
		return true;
	}

	@Override
	public boolean onOptionsItemSelected(MenuItem item) {
		// Handle action bar item clicks here. The action bar will
		// automatically handle clicks on the Home/Up button, so long
		// as you specify a parent activity in AndroidManifest.xml.
		int id = item.getItemId();
		if (id == R.id.action_settings) {
			return true;
		}
		return super.onOptionsItemSelected(item);
	}
}
