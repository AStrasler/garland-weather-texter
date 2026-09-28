# Decision rules

Location: Garland, Texas 75041. Garland is east of I-35. Times are America/Chicago.

## Numbers

The text uses NOAA/National Weather Service grid FWD/95,110.

- Daytime period supplies the high and the sky wording.
- Nighttime period supplies the low.
- Rain chance is the highest precipitation probability on that date.
- If the narrative forecast has a high but no following night period, the low comes from the NWS grid `minTemperature` for that evening.
- The next seven days start tomorrow when it is after 6:00 p.m. and today has no remaining daytime high.

OpenWeatherMap was tried and removed on 2026-09-28. Its free five-day feed disagreed with the local forecast and could not cover seven days. Do not add it back unless the owner asks. WeatherAPI was removed the same day because that key expired on 2026-10-05.

## Local TV text

Sources, when a same-day page can be read: WFAA, FOX 4, and NBC 5.

Discard the news text when its publication date is not today's America/Chicago date. Build the text from NOAA only in that case.

For the next 48 hours, if the news says storms are west of I-35, or west and northwest of the metroplex, and it does not also place them east of I-35 or in Garland, cap a high rain chance at 30 percent and call the sky mostly dry. Do not override a NOAA chance that is already 40 percent or lower.

If the news names Wednesday through Friday with storms, heavy rain, or flooding, those days can be worded as storms or flood risk. NOAA still supplies the temperature and rain percentage.

## Message shape

No test label, greeting, or source line.

One sentence on the week, then each day separated by a blank line:

```
Emoji Day: Sky.
High: 00°F, Low: 00°F. Rain: 00%.
```

Active NWS alerts go at the bottom, prefixed with 🚨. If none are active, say so with the same emoji. There is no character cap.

Suggested icons: clear or sunny ☀️, partly cloudy ⛅, overcast ☁️, rain 🌧️, thunderstorms ⛈️, high heat 🥵, gusts 💨. A slight storm chance uses ⛅, not the storm icon. Heat and wind icons can combine with the sky icon.

## Alerts as issued

Every 15 minutes, fetch active alerts for the point. Text only a new alert ID, or the same ID if its update time is newer. Do not send a message when nothing is new. Do not mark an alert sent until delivery is accepted. Keep sent IDs for 14 days.

## Subscribers

Someone must text the weather line before they can be added. A name on the approved list can be added when their text matches that name, then they receive `templates/welcome.txt` exactly.

Anyone else is not added and does not get the welcome. Tell the owner once and wait for a yes.

Approved people may never opt in. Do not remind the owner merely because they have not texted.

The Thursday 3:00 p.m. check exists to catch an unapproved join attempt. It does not add that person.
