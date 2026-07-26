// Sedona Trip Pin Data
// Each location includes: type, name, coords, description, links, and an embedded YouTube video
const PINS = [
  {
    id: 'basecamp',
    category: 'basecamp',
    name: 'BASECAMP — FR 525 / Loy Butte Rd',
    short: 'Dispersed camping hub',
    lat: 34.8796728,
    lng: -111.906977,
    difficulty: null,
    distance: null,
    description: `Central base for the whole trip. Five designated dispersed camping areas along Forest Road 525 (Loy Butte Rd): <strong>Surprise, Windmill, Cockscomb, Greasy Spoon, and Nolan</strong>. Nolan is the largest at ~12 acres — target this for the group with the Promaster and F250. Free, 14-day max stay on Coconino National Forest land. Graded dirt road, easy access for both rigs. No water, no toilets, no services — fully self-contained. <strong>Get in Sunday-Tuesday; sites fill by Friday afternoon.</strong>`,
    tips: [
      'No cell service in spots — download offline maps',
      'Showers: Cottonwood (20 min SW) has the best deal',
      'Water fill: Sedona town or Cottonwood',
      'Quiet hours enforced; respect neighbors'
    ],
    youtube: null,
    links: [
      { label: 'Coconino NF Camping Info', url: 'https://www.fs.usda.gov/r03/coconino/alerts/west-sedona-camping-and-campfire-restrictions' },
      { label: 'Google Maps', url: 'https://maps.google.com/?cid=9398216855430504381' },
      { label: 'Dispersed Camping Guide', url: 'https://bermstyle.com/dispersed-camping-in-sedona-a-vanlife-guide/' }
    ]
  },
  {
    id: 'thunder-mtn',
    fromBasecamp: '18 mi · 35 min from basecamp',
    category: 'shop',
    name: 'Thunder Mountain Bikes',
    short: 'Trail beta & tune-ups',
    lat: 34.863256,
    lng: -111.7897211,
    difficulty: null,
    description: `Best shop in Sedona for rentals, repairs, and current trail conditions. Stop here on day 1 — they'll give you the real beta on which trails are riding well, what's washed out, and the local shuttle situation. Open 9-6 daily.`,
    tips: [
      'Phone: 928-282-1106',
      'Ask about the free Sedona Shuttle for point-to-point rides',
      'They rent eBikes (limited routes) and full-suspension MTBs'
    ],
    youtube: null,
    links: [
      { label: 'Official Site', url: 'https://www.thundermountainbikes.com/' },
      { label: 'eBike Routes', url: 'https://thundermountainbikes.com/pages/ebike-trails-in-sedona' }
    ]
  },

  // MOUNTAIN BIKING
  {
    id: 'aerie',
    fromBasecamp: '4 mi · 12 min from basecamp',
    favorite: true,
    suggested: true,
    suggestedBy: 'Intermediate Suggestion from YouTube @ronsanderson99',
    category: 'mtb',
    name: 'Aerie / Cockscomb Loop',
    short: 'MTB — Intermediate, 6.1 mi',
    lat: 34.885763499999996,
    lng: -111.86983440000002,
    difficulty: 'Intermediate (Blue)',
    distance: '6.1 mi loop',
    description: `Perfect day-1 shakedown ride. Flowy berms, rolling singletrack, and bermed turns wrapping around Doe Mountain with views of Boynton Spires. Minutes from basecamp. Bikers prefer this over hikers so foot traffic is light. Can be extended to Mescal/Chuckwagon for a longer day.`,
    tips: [
      'Park at Aerie Trailhead (small lot, fills quickly)',
      'Extend via Dawa → Arizona Cypress for a full "Dry Creek Loop"',
      'Great views across to Boynton spires'
    ],
    youtube: 'https://www.youtube.com/embed/q4NN2w0RmbA',
    youtubeTitle: 'Aerie to Cockscomb POV — Sedona MTB',
    links: [
      { label: 'Trailforks: Aerie', url: 'https://www.trailforks.com/region/sedona/' },
      { label: 'Sedona MTB Guide', url: 'https://www.twowheeledwanderer.com/posts/mountain-biking-sedona/' }
    ]
  },
  {
    id: 'mescal',
    fromBasecamp: '13 mi · 25 min from basecamp',
    favorite: true,
    suggested: true,
    suggestedBy: 'Intermediate Suggestion from YouTube @ronsanderson99',
    category: 'mtb',
    name: 'Mescal Trail',
    short: 'MTB — Intermediate, slickrock classic',
    lat: 34.9018156,
    lng: -111.82673129999999,
    difficulty: 'Intermediate (Blue)',
    distance: '~2.5 mi each way',
    description: `One of the most beautiful trails in Sedona. Mescal runs along the base of Mescal Mountain on red slickrock with constant views back across to Boynton, Mescal Mountain, and the Boynton spires. Not super technical, but minor exposure and a few tricky maneuvers. Pairs perfectly with Chuckwagon for a 12-15 mile flowy day.`,
    tips: [
      'Park at Mescal Trailhead off Long Canyon Rd',
      'Combine with Chuckwagon for a true Sedona flow day',
      'Connects to Devil\'s Bridge — bring shoes if you want to hike it after'
    ],
    youtube: 'https://www.youtube.com/embed/CoQZFWatgU0',
    youtubeTitle: 'Mescal Trail Sedona MTB POV',
    links: [
      { label: 'AllTrails: Mescal', url: 'https://www.alltrails.com/us/arizona/sedona/mountain-biking' },
      { label: 'Singletracks Detail', url: 'https://www.singletracks.com/bike-trails/mescal-aerie-etc/' }
    ]
  },
  {
    id: 'chuckwagon',
    fromBasecamp: '13 mi · 25 min from basecamp',
    note: 'Looks very easy/basic, but might be a good warmup.',
    suggested: true,
    suggestedBy: 'Intermediate Suggestion from YouTube @ronsanderson99',
    category: 'mtb',
    name: 'Chuck Wagon Trail',
    short: 'MTB — Sedona\'s purest flow',
    lat: 34.8896492,
    lng: -111.8234664,
    difficulty: 'Intermediate (Blue)',
    distance: '~4 mi',
    description: `Arguably Sedona's truest flow trail — swoopy red dirt that's so grippy it buzzes under the tires. Watch out for hikers in the first mile (it doubles as the back-door route to Devil's Bridge), but crowds thin after. Connects to Mescal, Aerie, and the Devil's Bridge area for huge loop options.`,
    tips: [
      'Crowded in the first mile — be courteous, hikers have right of way',
      'Pedal in to Devil\'s Bridge to skip the hiker traffic',
      'Best ridden as part of a Mescal/Chuckwagon/Aerie loop'
    ],
    youtube: 'https://www.youtube.com/embed/1ggFmQ87VPQ',
    youtubeTitle: 'Sedona MTB Trail Guide: Chuck Wagon, Mescal, Aerie Loop',
    links: [
      { label: 'Trail Map', url: 'https://www.alltrails.com/us/arizona/sedona/mountain-biking' }
    ]
  },
  {
    id: 'hiline',
    fromBasecamp: '24 mi · 45 min from basecamp',
    category: 'mtb',
    name: 'Hiline Trail',
    short: 'MTB — DOUBLE BLACK, exposure',
    lat: 34.8045973,
    lng: -111.7713605,
    difficulty: 'Expert (Double Black)',
    distance: '~8 mi loop',
    description: `One of the Triple H (Hiline, Hangover, Hogs) — Sedona's bucket-list expert trails. Highly exposed singletrack cuts across a large ridge with massive cliff exposure and NO bailout until the end. Best done as a loop: <strong>Hiline → Baldwin → Templeton → Hermit</strong>. Killer views of Cathedral Rock the entire way.`,
    tips: [
      '⚠️ Cliff exposure is real. Don\'t ride tired or scared.',
      'Start from Yavapai Trailhead',
      'Climb up Hiline (it\'s techy but rideable), descend the loop',
      'Hardtail Party / BKXC have great walkthrough videos'
    ],
    youtube: 'https://www.youtube.com/embed/qCSTNUheiFY',
    youtubeTitle: 'Hiline Trail Sedona Arizona — MTB POV',
    links: [
      { label: 'Trailforks: Hiline', url: 'https://www.trailforks.com/trails/hiline/' },
      { label: 'Sedona MTB Trail Guide', url: 'https://www.youtube.com/watch?v=DG7Kus32xNg' }
    ]
  },
  {
    id: 'hangover',
    fromBasecamp: '22 mi · 42 min from basecamp',
    danger: true,
    category: 'mtb',
    name: 'Hangover Trail',
    short: 'MTB — HARDEST in Sedona',
    lat: 34.8664442,
    lng: -111.7484216,
    difficulty: 'Expert (Double Black)',
    distance: '~8 mi loop',
    description: `The hardest trail in Sedona. Brutal exposure, steep technical climbs, and slickrock ramps with serious consequences for mistakes. The Triple H crown jewel — only attempt if your crew is fully dialed and you're not afraid of heights. Access via Munds Wagon Trailhead off Schnebly Hill Rd.`,
    tips: [
      '⚠️ "One false move and you\'re a goner" — every rider says this',
      'Park at Munds Wagon TH — high clearance helpful',
      'Ride Cow Pies → up to Hangover for the standard loop',
      'Don\'t ride solo. Don\'t ride if tired. Don\'t ride in the rain.'
    ],
    youtube: 'https://www.youtube.com/embed/AnLyfbSMLFs',
    youtubeTitle: 'PLENTY to be scared of on Hangover — BKXC',
    links: [
      { label: 'Trailforks: Hangover', url: 'https://www.trailforks.com/trails/hangover/' },
      { label: 'How to Ride Slickrock — Guide', url: 'https://www.youtube.com/watch?v=1uAuGopEgOo' }
    ]
  },
  {
    id: 'broken-arrow-mtb',
    fromBasecamp: '22 mi · 40 min from basecamp',
    danger: true,
    note: 'Need to watch this one more closely before deciding whether to attempt.',
    category: 'mtb',
    name: 'Broken Arrow → Hogs',
    short: 'MTB — Expert, techy red rock',
    lat: 34.8455491,
    lng: -111.7568893,
    difficulty: 'Expert (Black/Double Black)',
    distance: '~10 mi loop',
    description: `Many riders' favorite Sedona ride. Techy red rock obstacles, slickrock ramps, and the iconic pedal out to <strong>Chicken Point overlook</strong>. The "Hogs" trio (Hog Wash, Hog Heaven, High on the Hog) adds advanced tech with exposure. Note: shared with Pink Jeep tours and OHV traffic — busy and dusty.`,
    tips: [
      'Trailhead closed Sat/Sun per current FS hours — go weekdays',
      'Lots of OHV/Jeep traffic, be alert',
      'Chicken Point is a MUST stop for photos',
      'Combine with the Hogs for a full expert day'
    ],
    youtube: 'https://www.youtube.com/embed/Afuup-2z-14',
    youtubeTitle: 'Sedona Double Black MTB — Broken Arrow / High on the Hog / Hog Heaven',
    links: [
      { label: 'Coconino NF: Broken Arrow', url: 'https://www.fs.usda.gov/recarea/coconino/recarea/?recid=55250' },
      { label: 'Triple H Guide', url: 'https://57hours.com/review/sedona-mountain-bike-trails/' }
    ]
  },
  {
    id: 'slim-shady',
    fromBasecamp: '24 mi · 43 min from basecamp',
    favorite: true,
    note: 'Looks pretty quick, but not super duper challenging. Pair with Llama + Bell Rock Pathway as a shuttle (see "Shuttle Run" pin).',
    category: 'mtb',
    name: 'Slim Shady',
    short: 'MTB — Intermediate flow classic',
    lat: 34.8260,
    lng: -111.7773,
    difficulty: 'Intermediate (Blue)',
    distance: '2.3 mi one-way',
    description: `Pure flow trail south of Bell Rock — bermed turns, rollers, and a few small drops on grippy red dirt. One of the best "intro to Sedona" rides for an intermediate group. Often linked with HT + Templeton for a longer Yavapai-area loop. Drains well — usually rideable when the high-altitude clay is sticky.`,
    tips: [
      'Best ridden top-down from Bell Rock TH',
      'Connects to HT and Llama for a full loop',
      'Crowded weekends — go midweek or early'
    ],
    youtube: 'https://www.youtube.com/embed/AwW-VdsjWOU',
    youtubeTitle: 'Best Mountain Biking in Sedona, AZ — Slim Shady',
    links: [
      { label: 'Trailforks: Slim Shady', url: 'https://www.trailforks.com/trails/slim-shady/' }
    ]
  },
  {
    id: 'llama',
    fromBasecamp: '25 mi · 45 min from basecamp',
    favorite: true,
    suggested: true,
    suggestedBy: 'Intermediate Suggestion from YouTube @ronsanderson99',
    note: 'Best ridden top-down as part of the Llama → Slim Shady → Bell Rock shuttle (see "Shuttle Run" pin).',
    category: 'mtb',
    name: 'Llama Trail',
    short: 'MTB — Intermediate flow with tech bits',
    lat: 34.8049,
    lng: -111.7784,
    difficulty: 'Intermediate (Blue)',
    distance: '3.2 mi',
    description: `Sweeping intermediate single in the Yavapai trail network. Mostly flow with a handful of rocky pinch points that keep you honest. Pairs well with HT, Templeton, and Made in the Shade for a 12-15 mile loop day. More character than your average flow trail without crossing into expert territory.`,
    tips: [
      'Park at Yavapai Vista or HT trailhead',
      'Ride as part of a Yavapai-area loop',
      'Lots of intersections — bring an offline map'
    ],
    youtube: 'https://www.youtube.com/embed/fHTzp09gkjU',
    youtubeTitle: 'Introduction to Sedona Mountain Biking — Llama Trail',
    links: [
      { label: 'Trailforks: Llama', url: 'https://www.trailforks.com/trails/llama-67225/' }
    ]
  },
  {
    id: 'templeton',
    fromBasecamp: '22 mi · 40 min from basecamp',
    category: 'mtb',
    name: 'Templeton',
    short: 'MTB — Cathedral Rock views',
    lat: 34.8351,
    lng: -111.7977,
    difficulty: 'Intermediate (Blue)',
    distance: '3.9 mi one-way',
    description: `One of the most photographed intermediate trails in the U.S. — runs along the base of Cathedral Rock with constant red rock views. Some exposure and technical slickrock features, but stays at intermediate grade overall. The standard descent option off the Hiline loop. Combine with Baldwin + HT for the classic Yavapai-to-Cathedral linkup.`,
    tips: [
      'Park at Yavapai Vista TH (south) or Bell Rock (north)',
      'Photo stop: the singletrack directly below Cathedral',
      'Pairs with Hiline as the descent option'
    ],
    youtube: 'https://www.youtube.com/embed/0PDj1DEbXeg',
    youtubeTitle: 'Best All-Around Bike Loop in Sedona — Cathedral Rock (Templeton)',
    links: [
      { label: 'Trailforks: Templeton', url: 'https://www.trailforks.com/trails/templeton/' }
    ]
  },
  {
    id: 'hog-wash',
    fromBasecamp: '22 mi · 42 min from basecamp',
    category: 'mtb',
    name: 'Hog Wash',
    short: 'MTB — Expert tech, exposure',
    lat: 34.8639,
    lng: -111.7456,
    difficulty: 'Expert (Black/Double Black)',
    distance: '~3 mi',
    description: `Part of the famous "Hogs" trio — Hog Wash gets into the gnarliest exposure of the three. Technical slickrock with cliff-edge sections and a few mandatory commits. Best ridden after warming up on Cow Pies or Mitten Ridge. Pairs with Hangover or Broken Arrow for a full Triple H day.`,
    tips: [
      '⚠️ Real exposure — comparable to Hangover',
      'Access via Munds Wagon TH off Schnebly Hill Rd',
      'Best ridden in the morning before Jeep tour traffic'
    ],
    youtube: 'https://www.youtube.com/embed/pJzDApCDQoA',
    youtubeTitle: 'Hog Heaven, High on the Hog, Hogwash — Sedona MTB',
    links: [
      { label: 'Trailforks: Hog Wash', url: 'https://www.trailforks.com/trails/hog-wash/' }
    ]
  },
  {
    id: 'western-civ',
    fromBasecamp: '28 mi · 48 min from basecamp',
    category: 'mtb',
    name: 'Western Civilization → Lime Kiln',
    short: 'MTB — Long Verde Valley flow',
    lat: 34.7892,
    lng: -111.8025,
    difficulty: 'Intermediate (Blue)',
    distance: '~12 mi one-way',
    description: `Long flowy connector that drops out of the high country down into Verde Valley — bigger views, smaller crowds, and zero technical surprises. A great "rest day" ride that still feels like an adventure. Shuttle-able if you can spot a truck at Dead Horse Ranch State Park.`,
    tips: [
      'Best as a one-way shuttle ride',
      'Quieter than the in-town Sedona trails',
      'Long — bring extra water and snacks'
    ],
    youtube: null,
    youtubeTitle: 'Sedona MTB POV',
    links: [
      { label: 'Trailforks: Lime Kiln', url: 'https://www.trailforks.com/region/sedona/' }
    ]
  },
  {
    id: 'girdner',
    fromBasecamp: '10 mi · 22 min from basecamp',
    category: 'mtb',
    name: 'Girdner Trail',
    short: 'MTB — Intermediate desert single',
    lat: 34.8898,
    lng: -111.7984,
    difficulty: 'Intermediate (Blue)',
    distance: '~5 mi',
    description: `Underrated intermediate single threading the desert north of west Sedona. Rolling terrain, occasional wash crossings, a handful of techy pinches. Connects the Aerie/Chuckwagon network on the west to the Dry Creek network on the east — useful linkage for "all-day" loop builders.`,
    tips: [
      'Park at Andante TH or Aerie',
      'Use as a connector — not usually a destination on its own',
      'Watch for cow patties in spring'
    ],
    youtube: 'https://www.youtube.com/embed/d9YBuvKLGiI',
    youtubeTitle: 'Sweet Sedona Singletrack — One Lap, Girdner Trail',
    links: [
      { label: 'Trailforks: Girdner', url: 'https://www.trailforks.com/trails/girdner/' }
    ]
  },
  {
    id: 'scorpion',
    fromBasecamp: '~13 mi · 25 min via 89A and Upper Red Rock Loop Rd',
    suggested: true,
    suggestedBy: 'Intermediate Suggestion from YouTube @ronsanderson99',
    category: 'mtb',
    name: 'Scorpion',
    short: 'MTB — Intermediate, 2.1 mi tech-flow descent',
    lat: 34.8462,
    lng: -111.8286,
    difficulty: 'Intermediate (Blue)',
    distance: '2.1 mi',
    description: `A Carroll Canyon hidden gem that starts near Red Rock High School and trends downhill with embedded basalt rock features punctuating an otherwise flowy line. About halfway through, the optional <strong>Pyramid spur</strong> peels off for advanced riders who want a techier descent. Best ridden north-to-south as a descent; works as part of a Skywalker / Herkenham / Ramshead loop.`,
    tips: [
      'Park at Red Rock HS lot for the classic top-down rip',
      'Pair with Pyramid for a more technical full descent',
      'Multi-directional — expect uphill traffic',
      'Avoid right after rain; basalt embedded sections get slick'
    ],
    youtube: 'https://www.youtube.com/embed/S5RTeiIzM70',
    youtubeTitle: 'Scorpion MTB Trail 4K POV — Sedona, AZ',
    links: [
      { label: 'Trailforks', url: 'https://www.trailforks.com/trails/scorpion-48867/' },
      { label: 'MTBProject', url: 'https://www.mtbproject.com/trail/7038545/scorpion' }
    ]
  },
  {
    id: 'outer-limits',
    fromBasecamp: '~5 mi · 12 min via Dry Creek Rd',
    suggested: true,
    suggestedBy: 'Intermediate Suggestion from YouTube @ronsanderson99',
    category: 'mtb',
    name: 'Outer Limits',
    short: 'MTB — Intermediate, 6.3 mi flow epic',
    lat: 34.8801,
    lng: -111.8634,
    difficulty: 'Intermediate (Blue)',
    distance: '6.3 mi',
    description: `Sedona's longest sustained flow line, opened 2019. From the Aerie/Cultural Park end it rolls fast through dips, rock gardens, and corners along the base of the Cockscomb. <strong>One short exposed section above Dry Creek</strong> and a steep techy zig-zag drop into the canyon give intermediates a few hike-a-bike moments. Easiest direction NW-to-SE.`,
    tips: [
      'Park at Cultural Park or Aerie trailhead — both add easy access',
      'Combine with Last Frontier or Girdner for a 12+ mi loop',
      'The Dry Creek exposure section is walkable — no shame',
      'eBikes prohibited; dogs OK on leash'
    ],
    youtube: 'https://www.youtube.com/embed/NzHnV25NgNU',
    youtubeTitle: 'The Longest Flow Trail in Sedona, Outer Limits!',
    links: [
      { label: 'Trailforks', url: 'https://www.trailforks.com/trails/outer-limits-170415/' },
      { label: 'MTBProject', url: 'https://www.mtbproject.com/trail/7051886/outer-limits' }
    ]
  },
  {
    id: 'adobe-jack',
    fromBasecamp: '~13 mi · 22 min via 89A through Sedona',
    suggested: true,
    suggestedBy: 'Intermediate Suggestion from YouTube @ronsanderson99',
    category: 'mtb',
    name: 'Adobe Jack',
    short: 'MTB — Intermediate, 1.9 mi in-town singletrack',
    lat: 34.8838,
    lng: -111.7811,
    difficulty: 'Intermediate (Blue)',
    distance: '1.9 mi',
    description: `A short but characterful in-town trail running between the Adobe Jack lot off 89A and the Jordan trail near the Sink Hole. The route weaves through dry wash sections and narrow climbing pinches that <strong>play more advanced than the Blue rating suggests</strong>. Great glue piece for stitching together a Soldier's Wash loop with Jordan, Javelina, and Crusty.`,
    tips: [
      'Parking lot is tiny (4–5 spots) — arrive early or bike from town',
      'North-to-south rides faster; S-to-N is better for a bigger loop',
      'A couple of narrow climbs may force a walk for intermediates',
      'Combine with Grand Central / Javelina for a 6–10 mi day'
    ],
    youtube: 'https://www.youtube.com/embed/Mtc9v2q_LeM',
    youtubeTitle: 'Adobe Jack — Sedona Trail Guide (Thunder Mountain Bikes)',
    links: [
      { label: 'Trailforks', url: 'https://www.trailforks.com/trails/adobe-jack/' },
      { label: 'MTBProject', url: 'https://www.mtbproject.com/trail/4920585/adobe-jack-grand-central-loop' }
    ]
  },
  {
    id: 'little-rock',
    fromBasecamp: '~20 mi · 32 min via 89A then Hwy 179 to Jack\'s Canyon',
    suggested: true,
    suggestedBy: 'Intermediate Suggestion from YouTube @ronsanderson99',
    category: 'mtb',
    name: 'Little Rock',
    short: 'MTB — Intermediate, ~2.5 mi flowy slickrock XC',
    lat: 34.7848,
    lng: -111.7322,
    difficulty: 'Intermediate (Blue)',
    distance: '~2.5 mi',
    description: `A newer Big Park trail in the Village of Oak Creek that bisects the VOC loop with fast classic XC singletrack and one rippable slickrock section. Mostly true intermediate with a couple of tricky punches; rolling enough that the climb sneaks by. <strong>Best paired with Rabbit Ears as the standard 5.9 mi loop.</strong>`,
    tips: [
      'Park at Jack\'s Canyon trailhead — less crowded than Bell Rock lots',
      'Always ride as a loop with Rabbit Ears for the full experience',
      'Higher equestrian use than most Sedona trails — yield politely',
      'Great cold-day option — lower elevation than west-side trails'
    ],
    youtube: 'https://www.youtube.com/embed/M6TZvJE77as',
    youtubeTitle: 'Best Intermediate MTB Trail in Sedona — Little Rock & Rabbit Ears',
    links: [
      { label: 'Trailforks', url: 'https://www.trailforks.com/trails/little-rock-423832/' },
      { label: 'MTBProject (loop)', url: 'https://www.mtbproject.com/trail/7072176/rabbit-ears-little-rock-loop' }
    ]
  },
  {
    id: 'rabbit-ears',
    fromBasecamp: '~20 mi · 32 min via 89A and Hwy 179 to Jack\'s Canyon',
    suggested: true,
    suggestedBy: 'Intermediate Suggestion from YouTube @ronsanderson99',
    category: 'mtb',
    name: 'Rabbit Ears',
    short: 'MTB — Intermediate, 2.5 mi climb-then-descend',
    lat: 34.7850,
    lng: -111.7322,
    difficulty: 'Intermediate (Blue)',
    distance: '2.5 mi',
    description: `Opened 2021. Starts with a grindy ~1.5 mi climb out of Jack's Canyon, then pays you back with a long natural-flow descent featuring views west to Courthouse Butte, Bell Rock, and the namesake Rabbit Ears spire. <strong>~450 ft gain.</strong> Moderate tech, big rewards, low crowds compared to Bell Rock Pathway.`,
    tips: [
      'Park at Jack\'s Canyon trailhead off Big Park / 179',
      'Best as a loop with Little Rock (~5.9 mi total)',
      'Both directions work, but climb first / descend west is the move',
      'Mostly exposed — not a great midday summer ride'
    ],
    youtube: 'https://www.youtube.com/embed/-5BPMRFcugQ',
    youtubeTitle: 'Riding Rabbit Ears in Sedona, Arizona with Alex Petitdemange',
    links: [
      { label: 'Trailforks', url: 'https://www.trailforks.com/trails/rabbit-ears-425649/' },
      { label: 'MTBProject', url: 'https://www.mtbproject.com/trail/7072172/rabbit-ears' }
    ]
  },
  {
    id: 'axis',
    fromBasecamp: '~7 mi · 15 min via Dry Creek Rd and 89A',
    suggested: true,
    suggestedBy: 'Intermediate Suggestion from YouTube @ronsanderson99',
    category: 'mtb',
    name: 'Axis',
    short: 'MTB — Intermediate, 3.2 mi flowy connector',
    lat: 34.8550,
    lng: -111.8327,
    difficulty: 'Intermediate (Blue)',
    distance: '3.2 mi',
    description: `A Western Gateway workhorse that connects Cultural Park across Dry Creek to the Cockscomb trail system. The first segment to Lasso is fast and clear-sighted; the climb half pitches up into a <strong>Black-rated effort</strong>, then the lower mile tilts back downhill through two fast wide slickrock drainages — the highlight of the trail.`,
    tips: [
      'Start at Cultural Park lot — free, big, and rarely full',
      'Climb is sneaky-hard (Black climb rating) despite the Blue label',
      'Stitch into a Roundabout → Girdner → Axis → Bolo → LF → Outer Limits loop',
      'eBikes prohibited'
    ],
    youtube: 'https://www.youtube.com/embed/hqj2tgKCILE',
    youtubeTitle: 'Mountain Biking in Sedona, AZ — Axis and Girdner Trail',
    links: [
      { label: 'Trailforks', url: 'https://www.trailforks.com/trails/axis/' },
      { label: 'MTBProject', url: 'https://www.mtbproject.com/trail/7065533/axis' }
    ]
  },

  {
    id: 'shuttle-llama-slim',
    fromBasecamp: '24 mi · 45 min from basecamp (drop) · pickup 26 mi · 48 min',
    category: 'mtb',
    name: 'Shuttle Run: Llama → Slim Shady → Bell Rock Pathway',
    short: 'MTB — Blue, ~6-7 mi, mostly descending, shuttleable',
    lat: 34.82174,
    lng: -111.77177,
    difficulty: 'Intermediate (Blue)',
    distance: '~6-7 mi, ~400-500 ft net descent',
    description: `The cleanest Blue-grade "drop and ride" line in Sedona. Drop at <strong>Little Horse Trailhead</strong> (Hwy 179, milepost ~309.8), ride Llama → Slim Shady → Bell Rock Pathway south to <strong>Bell Rock Vista</strong> for pickup. Both ends sit on paved Hwy 179, and the free Sedona Shuttle covers Little Horse Thu–Sun (no driver needed). Twisty red-dirt singletrack with short slickrock bits and big Bell Rock / Courthouse views. No cliff exposure, no mandatory features. <strong>Sedona doesn't have a true Whistler-style gravity descent</strong> — expect short pedaly bits between the descending sections — but this is as close as it gets at the Blue grade.`,
    tips: [
      'Drop: Little Horse TH (34.82174, -111.77177)',
      'Pickup: Bell Rock Vista TH (~34.792, -111.767), a few miles south on Hwy 179',
      'Free Sedona Shuttle covers Little Horse Thu–Sun — skip the driver',
      'Ride north-to-south for the descent character',
      'Combines two trails already on the map (Llama + Slim Shady) into one continuous shuttle line'
    ],
    youtube: null,
    links: [
      { label: 'Trailforks: Slim Shady', url: 'https://www.trailforks.com/trails/slim-shady/' },
      { label: 'MTB Project: Bell Rock', url: 'https://www.mtbproject.com/trail/4915849/bell-rock-trail' },
      { label: 'Sedona Shuttle Schedule', url: 'https://sedonashuttle.com/trailhead-shuttles/' }
    ]
  },
  {
    id: 'shuttle-templeton',
    fromBasecamp: '24 mi · 45 min from basecamp (drop) · pickup 22 mi · 40 min',
    category: 'mtb',
    name: 'Shuttle Run: Templeton → HT',
    short: 'MTB — Mostly Blue, one Black pitch most walk',
    lat: 34.82174,
    lng: -111.77180,
    difficulty: 'Blue with one Black pitch',
    distance: '~3.5 mi, mostly descending',
    note: 'One Black section near the finish (Cathedral Rock → Oak Creek pitch) — even strong intermediates often walk it. Bring shoes for hike-a-bike.',
    description: `Shorter shuttleable descent option. Drop at <strong>Little Horse Trailhead</strong> (Hwy 179), ride Templeton + HT connector, pickup at <strong>Back O' Beyond TH</strong> on the west side. Mostly Blue character with iconic Cathedral Rock views the whole way down. Stacks on the same Little Horse drop as the Llama line, so you can do both in one shuttle day.`,
    tips: [
      'Drop: Little Horse TH (34.82174, -111.77177)',
      'Pickup: Back O\' Beyond TH (~34.827, -111.790)',
      '⚠️ One Black pitch at the finish — walk it if you need',
      'Pairs naturally as the "second run" after the Llama → Slim Shady shuttle',
      'Iconic Cathedral Rock views the whole descent'
    ],
    youtube: null,
    links: [
      { label: 'MTB Project: Templeton', url: 'https://www.mtbproject.com/trail/594263/templeton-trail' },
      { label: 'Trailforks: Templeton', url: 'https://www.trailforks.com/trails/templeton-15041/' }
    ]
  },

  // E-DIRT BIKE / OHV
  {
    id: 'outlaw-ohv',
    fromBasecamp: '6 mi · 18 min from basecamp',
    category: 'ohv',
    name: 'Outlaw Trail (OHV)',
    short: 'E-Dirt Bike — 10.5 mi loop',
    lat: 34.9367868,
    lng: -111.9344421,
    difficulty: 'Moderate OHV',
    distance: '10.5 mi loop',
    description: `Classic Sedona OHV route starting from Honanki Heritage Site. Rocky old wagon trail through west canyon gulches with stunning red rock views and a stop at ancient cliff dwellings. Lighter traffic than Broken Arrow. Connects to Ranch Loop and Diamondback Gulch for a full day. 15 min from basecamp.`,
    tips: [
      'Watch a Sur-Ron POV: linked below — same bike, same trail',
      'Stop at Honanki Heritage Site (free with Red Rock Pass)',
      'Combine with Diamondback Gulch for a full day from camp',
      '15 mph speed limit, helmet required'
    ],
    youtube: 'https://www.youtube.com/embed/XFNRBWFgUiM',
    youtubeTitle: 'SUR-RON on Outlaw OHV Trail — Sedona',
    links: [
      { label: 'Coconino NF: Sedona OHV Routes', url: 'https://www.fs.usda.gov/r03/coconino/recreation/sedona-area-ohv-routes' },
      { label: 'Trail Guide', url: 'https://livethatadventure.com/how-to-drive-outlaw-diamondback-gulch-4wd-trails-in-sedona/' }
    ]
  },
  {
    id: 'diamondback',
    fromBasecamp: '1 mi · 3 min from basecamp (ride from tent)',
    favorite: true,
    category: 'ohv',
    name: 'Diamondback Gulch (OHV)',
    short: 'E-Dirt Bike — Nature\'s rollercoaster',
    lat: 34.885873,
    lng: -111.893423,
    difficulty: 'Advanced OHV',
    distance: '6 mi loop',
    description: `Borders the basecamp — ride from your tent. Known as "nature's rollercoaster" — the highlight is a ten-story descent in and out of the largest gulch in west Sedona. Steep climbs, off-camber sections, rocky ledges. Best run clockwise: <strong>start on Boynton Pass Road, end at FR 525</strong>.`,
    tips: [
      '⚠️ North section (152A) is slick clay if it rains — check forecast',
      'Watch for oncoming Jeeps; clockwise direction is most common',
      'Less scenic than Outlaw but way more technical fun',
      'Right next to camp — easy half-day ride'
    ],
    youtube: 'https://www.youtube.com/embed/nt-bhuRcZM4',
    youtubeTitle: 'Diamondback Gulch ATV Descent — Sedona',
    links: [
      { label: 'Trail Conditions', url: 'https://www.onxmaps.com/offroad/trails/us/arizona/diamondback-gulch' }
    ]
  },
  {
    id: 'broken-arrow-ohv',
    fromBasecamp: '22 mi · 40 min from basecamp',
    category: 'ohv',
    name: 'Broken Arrow (OHV)',
    short: 'E-Dirt Bike — THE Sedona ride',
    lat: 34.8455491,
    lng: -111.7568893,
    difficulty: 'Advanced OHV',
    distance: '4 mi RT',
    description: `Sedona's quintessential off-road trail. 3.9 miles of slickrock obstacles, the <strong>Devil's Staircase</strong> climb, Submarine Rock, and the iconic Chicken Point overlook. Best views in Sedona from a vehicle. Likely your favorite day on the e-bikes — but trailer in, you can't legally ride street.`,
    tips: [
      '⚠️ Trailer in — Sur-Ron/Talaria not street legal',
      'Park at Broken Arrow Trailhead off Morgan Rd',
      'Air down for better traction if your bike has tubeless setup',
      'Submarine Rock + Chicken Point = mandatory photo stops',
      'Goes early — Pink Jeep tours start at 8am'
    ],
    youtube: 'https://www.youtube.com/embed/dOmbOfTzCnc',
    youtubeTitle: 'SUR-RON on Broken Arrow — Sedona',
    links: [
      { label: 'Coconino NF: Broken Arrow', url: 'https://www.fs.usda.gov/recarea/coconino/recarea/?recid=55250' },
      { label: 'Trail Map (onX)', url: 'https://www.onxmaps.com/offroad/trails/us/arizona/broken-arrow' }
    ]
  },
  {
    id: 'schnebly-ohv',
    fromBasecamp: '35 mi · 55 min from basecamp (I-17 side entry)',
    category: 'ohv',
    name: 'Schnebly Hill Rd (OHV)',
    short: 'E-Dirt Bike — Long cruise to the rim',
    lat: 34.88961,
    lng: -111.70316299999999,
    difficulty: 'Moderate OHV',
    distance: '11 mi one-way',
    description: `Climbs 2,200 ft from Sedona up to the Mogollon Rim with endless dirt road spurs at the top. Best accessed from the I-17 side (the Sedona-side approach is gnarly rocky). Once on top, you've got hours of forest roads to explore. Great long-range cruise for the e-bikes — bring extra battery.`,
    tips: [
      '⚠️ Bring spare batteries — this is a long ride',
      'Best entry: I-17 exit 320, head west',
      'Vista Overlook is the must-stop photo',
      'Forest road network at the top = endless exploring'
    ],
    youtube: 'https://www.youtube.com/embed/2RFZqFN_cmo',
    youtubeTitle: 'Sedona Off-Road — Broken Arrow, Soldier Pass, Schnebly Hill',
    links: [
      { label: 'Coconino NF Info', url: 'http://www.fs.usda.gov/recarea/coconino/recarea/?recid=55036&actid=64' }
    ]
  },
  {
    id: 'soldier-pass-ohv',
    fromBasecamp: '18 mi · 32 min from basecamp',
    category: 'ohv',
    name: 'Soldier Pass 4WD (FR9904)',
    short: 'E-Dirt Bike — Devil\'s Kitchen access',
    lat: 34.8826,
    lng: -111.7825,
    difficulty: 'Advanced OHV',
    distance: '4 mi RT',
    description: `Rocky 4WD road that doubles as the OHV access to Devil's Kitchen sinkhole and Seven Sacred Pools. More technical than it looks — boulder gardens and step-ups that gate out lifted Jeeps. Same red rock scenery as the hiking trail but seen at e-bike pace.`,
    tips: [
      '⚠️ Trailer in — Sur-Ron/Talaria not street legal in town',
      'Hiker traffic is heavy — go early',
      'Turnaround at Devil\'s Kitchen — beyond is wilderness, no OHV'
    ],
    youtube: 'https://www.youtube.com/embed/92Jrv6mLucA',
    youtubeTitle: 'Soldier Pass Off-Road 4x4 Trail — Sedona, Arizona',
    links: [
      { label: 'Coconino NF Info', url: 'https://www.fs.usda.gov/recarea/coconino/recarea/?recid=55392' }
    ]
  },
  {
    id: 'sycamore-pass',
    fromBasecamp: '5 mi · 15 min from basecamp (direct on FR525)',
    category: 'ohv',
    name: 'Sycamore Pass Rd (FR525C)',
    short: 'E-Dirt Bike — Cruise from basecamp',
    lat: 34.9482,
    lng: -111.9472,
    difficulty: 'Easy OHV',
    distance: '~14 mi one-way',
    description: `Easy graded dirt road continuation north of basecamp — links FR525 to the Sycamore Canyon Wilderness boundary. Big sky, big views into Sycamore Canyon, very little traffic. Perfect "wake-up" cruise or a rainy-day backup when the technical OHV is muddy. Loops back via FR761 / FR153 if you want a full day.`,
    tips: [
      'Direct from basecamp — no trailer needed',
      'Easy enough for first-time riders',
      'Sycamore Vista overlook is the turnaround photo'
    ],
    youtube: null,
    youtubeTitle: 'Sedona Off-Road',
    links: [
      { label: 'Coconino NF Info', url: 'https://www.fs.usda.gov/r03/coconino/recreation/sedona-area-ohv-routes' }
    ]
  },
  {
    id: 'van-deren',
    fromBasecamp: '8 mi · 18 min from basecamp',
    category: 'ohv',
    name: 'Van Deren Cabin Loop (FR152)',
    short: 'E-Dirt Bike — Historic + technical',
    lat: 34.8927,
    lng: -111.8364,
    difficulty: 'Moderate OHV',
    distance: '~7 mi loop',
    description: `Combines easy forest road cruising with a few proper technical sections through Dry Creek and past the historic Van Deren homestead. Mixed terrain — rocky climbs, sandy washes, loose descents. Good intermediate practice before tackling Broken Arrow or Hangover OHV terrain.`,
    tips: [
      '⚠️ Wash crossings can be deep after rain',
      'Pair with Diamondback for a full day from basecamp',
      'Historic markers along the route'
    ],
    youtube: 'https://www.youtube.com/embed/3S1EFI0rkAA',
    youtubeTitle: 'Van Deren Cabin via Vultee Arch Rd — Sedona, AZ',
    links: [
      { label: 'Coconino NF Info', url: 'https://www.fs.usda.gov/r03/coconino/recreation/sedona-area-ohv-routes' }
    ]
  },
  {
    id: 'last-frontier',
    fromBasecamp: '25 mi · 45 min from basecamp',
    category: 'ohv',
    name: 'Last Frontier 4WD',
    short: 'E-Dirt Bike — Quiet technical loop',
    lat: 34.8472,
    lng: -111.7341,
    difficulty: 'Moderate OHV',
    distance: '~6 mi',
    description: `Lesser-known east Sedona 4WD route that escapes the Pink Jeep parade on Broken Arrow. Mixed slickrock and rocky climbs with sweeping views into Bear Wallow Canyon. A solid "almost-Broken-Arrow" day without the crowds.`,
    tips: [
      '⚠️ Trailer in from basecamp',
      'Quieter than Broken Arrow with the same red rock terrain',
      'Pair with Schnebly Hill for a full east-side day'
    ],
    youtube: null,
    youtubeTitle: 'Sedona Off-Road',
    links: [
      { label: 'Coconino NF Info', url: 'https://www.fs.usda.gov/r03/coconino/recreation/sedona-area-ohv-routes' }
    ]
  },

  // HIKING
  {
    id: 'cathedral',
    fromBasecamp: '22 mi · 40 min from basecamp',
    category: 'hike',
    name: 'Cathedral Rock',
    short: 'Hike — Iconic, sunset must',
    lat: 34.8360908,
    lng: -111.7795925,
    difficulty: 'Hard (short but steep)',
    distance: '1.2 mi RT',
    description: `Sedona's signature hike. Short, steep scramble with rock-climbing moves up to the saddle between the spires. <strong>Vortex site</strong>. Best done for sunset — the rock glows red in the late light. Plan to be at the trailhead 90 min before sunset.`,
    tips: [
      '⚠️ Free shuttle Thu-Sun → trailhead lot is CLOSED those days',
      'Self-drive Mon-Wed, shuttle Thu-Sun',
      'Real scrambling — wear grippy shoes',
      'Bring a headlamp for the descent at dusk'
    ],
    youtube: 'https://www.youtube.com/embed/5EgZyc_SKmY',
    youtubeTitle: 'Cathedral Rock Guide — 4K',
    links: [
      { label: 'AllTrails', url: 'https://www.alltrails.com/trail/us/arizona/cathedral-rock-trail' },
      { label: 'Sedona Shuttle Schedule', url: 'https://sedonaaz.gov/your-government/departments/sedona-shuttle' }
    ]
  },
  {
    id: 'devils-bridge',
    fromBasecamp: '11 mi · 25 min from basecamp',
    category: 'hike',
    name: 'Devil\'s Bridge',
    short: 'Hike — Iconic arch, 4.2 mi',
    lat: 34.9030007,
    lng: -111.8141399,
    difficulty: 'Moderate',
    distance: '4.2 mi RT',
    description: `The largest sandstone arch in Sedona — the iconic Instagram photo. Mostly flat dirt road approach, then a steep final climb to the bridge. <strong>Hike it at sunrise to avoid the photo line.</strong> Bonus: ride your MTBs in via Chuckwagon to cut the walk-in significantly.`,
    tips: [
      'Arrive at the trailhead by 7am or expect to park a mile out',
      'Photo line at the bridge can be 25-30 min mid-day',
      'Park at Mescal TH for a shorter, prettier approach',
      'Skip this one Sat/Sun — absolutely zoo-level crowded'
    ],
    youtube: 'https://www.youtube.com/embed/5EgZyc_SKmY',
    youtubeTitle: 'Cathedral & Devil\'s Bridge Sedona Guide',
    links: [
      { label: 'AllTrails', url: 'https://www.alltrails.com/trail/us/arizona/devils-bridge-trail' },
      { label: 'Coconino NF Info', url: 'https://www.fs.usda.gov/recarea/coconino/recarea/?recid=55292' }
    ]
  },
  {
    id: 'boynton',
    fromBasecamp: '7 mi · 15 min from basecamp',
    category: 'hike',
    name: 'Boynton Canyon → Subway Cave',
    short: 'Hike — 6 mi, the Subway Cave',
    lat: 34.9073761,
    lng: -111.84845639999999,
    difficulty: 'Moderate',
    distance: '6 mi RT',
    description: `Six miles round-trip, ~4 hours. Easy canyon walking through ponderosa pine until the final climb to the <strong>Subway Cave</strong> — one of the most photogenic spots in the Southwest. The scramble up is moderate; once inside the cave the photo angle is iconic.`,
    tips: [
      'Take the social trail right at "the tree" ~2 miles in',
      'Two routes up to the cave — the slickrock ramp or the scramble on the left',
      'Closest icon to basecamp — start early',
      'Wildlife: mule deer, occasional bear'
    ],
    youtube: 'https://www.youtube.com/embed/KBAwwuD_few',
    youtubeTitle: 'Secret Subway Cave in Boynton Canyon — Sedona [4K]',
    links: [
      { label: 'Coconino NF Info', url: 'https://www.fs.usda.gov/recarea/coconino/recarea/?recid=55242' }
    ]
  },
  {
    id: 'soldier-pass',
    fromBasecamp: '18 mi · 32 min from basecamp',
    category: 'hike',
    name: 'Soldier Pass',
    short: 'Hike — Caves + Pools, 4.5 mi',
    lat: 34.8843579,
    lng: -111.783676,
    difficulty: 'Moderate',
    distance: '4.5 mi RT',
    description: `Best variety hike in Sedona. You get <strong>three landmarks in one trail</strong>: Devil's Kitchen sinkhole, the Seven Sacred Pools, and the spectacular Soldier Pass Cave at the top. Tiny trailhead lot — go before 8am or take the shuttle.`,
    tips: [
      '⚠️ Tiny lot — gate closes when full. Be there by 7am.',
      'Go RIGHT at the fork marked "wilderness" for the caves',
      'Caves are the highlight — keep going past the pools',
      'Final climb is moderate scrambling'
    ],
    youtube: 'https://www.youtube.com/embed/7unRDoSgIZ4',
    youtubeTitle: 'Sedona Series: Soldier Pass Trail & Cave',
    links: [
      { label: 'Coconino NF Info', url: 'https://www.fs.usda.gov/recarea/coconino/recarea/?recid=55392' }
    ]
  },
  {
    id: 'bell-rock',
    fromBasecamp: '25 mi · 45 min from basecamp',
    category: 'hike',
    name: 'Bell Rock Pathway',
    short: 'Hike — Easy, scramble optional',
    lat: 34.8243217,
    lng: -111.7755041,
    difficulty: 'Easy + optional scramble',
    distance: '3.6 mi loop',
    description: `Easy 3.6 mile loop around the base of Bell Rock with an optional scramble UP the rock itself for incredible views. <strong>Vortex site</strong>. Great rest-day hike or sunset stroll. Connects to Courthouse Butte Loop if you want to extend to 5+ miles.`,
    tips: [
      'Family-friendly base loop',
      'Scramble up the rock for the real reward',
      'Watch for mountain bikers — shared trail',
      'Good sunset option if Cathedral is too crowded'
    ],
    youtube: 'https://www.youtube.com/embed/mn6YLkskxgs',
    youtubeTitle: 'Bell Rock Hike — Sedona, Arizona',
    links: [
      { label: 'AllTrails', url: 'https://www.alltrails.com/trail/us/arizona/bell-rock' }
    ]
  },
  {
    id: 'fay-canyon',
    fromBasecamp: '5 mi · 12 min from basecamp',
    category: 'hike',
    name: 'Fay Canyon',
    short: 'Hike — Quiet sleeper pick',
    lat: 34.907742,
    lng: -111.8623673,
    difficulty: 'Easy',
    distance: '2.4 mi RT',
    description: `Quiet shaded canyon — a sleeper pick when the icons are overrun. Towering red walls on both sides. The side scramble up to <strong>Fay Arch</strong> halfway in is the reward, and you can scramble to a flat overlook rock at the very end. Right next to basecamp — perfect easy day after a hard ride.`,
    tips: [
      'Less crowded than the icons',
      'Look for the unmarked Fay Arch spur about halfway',
      'Great late-afternoon hike with shade'
    ],
    youtube: 'https://www.youtube.com/embed/KhPXSlEHeHo',
    youtubeTitle: 'Fay Canyon Walk-About — Sedona [4K]',
    links: [
      { label: 'Trail Info', url: 'https://www.fs.usda.gov/recarea/coconino/recarea/?recid=55296' }
    ]
  },
  {
    id: 'west-fork',
    fromBasecamp: '32 mi · 55 min from basecamp',
    category: 'hike',
    name: 'West Fork of Oak Creek',
    short: 'Hike — Stream crossings, fall colors',
    lat: 34.9909,
    lng: -111.7472,
    difficulty: 'Moderate',
    distance: '6.4 mi RT',
    description: `Sedona's all-time classic hike — a flat-ish creek-bottom walk through a red rock slot corridor with 13+ stream crossings and stands of yellow bigtooth maple lighting up in late October. Drive ~30 min north up Oak Creek Canyon. <strong>Peak fall color: third week of October — that's exactly when you're here.</strong>`,
    tips: [
      'Bring water shoes or be ready for wet feet',
      '$12 day-use fee at the trailhead',
      'Go on a weekday — fall foliage = packed parking',
      'Turnaround when you want — the hike-in is the destination'
    ],
    youtube: 'https://www.youtube.com/embed/48-ej46TWzw',
    youtubeTitle: 'West Fork Trail & Oak Creek Canyon — Fall Colors',
    links: [
      { label: 'Coconino NF Info', url: 'https://www.fs.usda.gov/recarea/coconino/recarea/?recid=55410' },
      { label: 'AllTrails', url: 'https://www.alltrails.com/trail/us/arizona/west-fork-trail-oak-creek' }
    ]
  },
  {
    id: 'birthing-cave',
    fromBasecamp: '11 mi · 22 min from basecamp',
    category: 'hike',
    name: 'Birthing Cave',
    short: 'Hike — Short iconic photo cave',
    lat: 34.8889,
    lng: -111.8230,
    difficulty: 'Easy + final scramble',
    distance: '2 mi RT',
    description: `Short flat walk-in followed by a steep slickrock scramble up to a curved hollow cave with one of the most iconic photo angles in Sedona. <strong>Vortex site.</strong> Often paired with the Long Canyon Trail as a half-day. Doable from basecamp in 10 minutes.`,
    tips: [
      'Photo line at the cave can be 10-15 min mid-day',
      'Final scramble is moderately exposed — take the right side',
      'Park at Long Canyon TH off Long Canyon Rd',
      'Hike at sunrise or after 3pm for best light'
    ],
    youtube: 'https://www.youtube.com/embed/JTr8X6QL9XQ',
    youtubeTitle: 'Sedona Secret Birthing Cave Guide [4K]',
    links: [
      { label: 'AllTrails', url: 'https://www.alltrails.com/trail/us/arizona/birthing-cave' }
    ]
  },
  {
    id: 'doe-mountain',
    fromBasecamp: '3 mi · 8 min from basecamp',
    category: 'hike',
    name: 'Doe Mountain',
    short: 'Hike — Mesa-top sunset, 1.6 mi',
    lat: 34.8927,
    lng: -111.8740,
    difficulty: 'Moderate (short steep)',
    distance: '1.6 mi RT',
    description: `Steep switchbacks up the side of Doe Mountain mesa, then a flat plateau on top with a 360° view of the entire west Sedona red rock fortress. <strong>One of the best sunset hikes in Sedona</strong> — and the trailhead is literally next to basecamp. The top is exposed; wind can be brutal.`,
    tips: [
      'Walking distance from basecamp',
      'Sunset is the move — bring a headlamp for descent',
      'Top is a big flat mesa — wander for 20 min before heading down',
      'Wind on top is no joke — bring a layer'
    ],
    youtube: 'https://www.youtube.com/embed/GEo3nuftl2M',
    youtubeTitle: 'Sunrise Hike to the Summit of Doe Mountain — Sedona',
    links: [
      { label: 'AllTrails', url: 'https://www.alltrails.com/trail/us/arizona/doe-mountain' }
    ]
  },
  {
    id: 'bear-mountain',
    fromBasecamp: '3 mi · 10 min from basecamp',
    category: 'hike',
    name: 'Bear Mountain',
    short: 'Hike — Strenuous, 1,900 ft climb',
    lat: 34.9094,
    lng: -111.8753,
    difficulty: 'Hard',
    distance: '5 mi RT',
    description: `The hardest mainstream hike in Sedona — relentless climbing with several false summits and real scrambling on slickrock pitches. Massive views across to Boynton, Doe Mountain, and the entire Mogollon Rim. <strong>Plan a full day — start before 8am.</strong> Trailhead is 5 minutes from basecamp.`,
    tips: [
      'Bring 3+ liters of water per person',
      'Multiple false summits — keep going to the real top',
      'Sun-exposed top to bottom — no shade',
      'Best in October temps — would be brutal in summer'
    ],
    youtube: 'https://www.youtube.com/embed/15X6LcNZRkg',
    youtubeTitle: 'Hiking Sedona\'s Epic Bear Mountain',
    links: [
      { label: 'AllTrails', url: 'https://www.alltrails.com/trail/us/arizona/bear-mountain-trail' }
    ]
  },
  {
    id: 'airport-mesa',
    fromBasecamp: '18 mi · 32 min from basecamp',
    category: 'hike',
    name: 'Airport Mesa Loop',
    short: 'Hike — Easy vortex sunset loop',
    lat: 34.8508,
    lng: -111.7905,
    difficulty: 'Easy',
    distance: '3.3 mi loop',
    description: `Easy loop around the perimeter of Airport Mesa with the most accessible sunset view in town. Includes the <strong>Airport Mesa Vortex</strong> — a short spur up a slickrock ridge for the energy-work folks. Great for jet-lagged arrival day or for resting tired legs mid-trip.`,
    tips: [
      'Sunset crowds at the overlook — go for the loop, skip the lot',
      'Vortex spur is short and worth it',
      '$3 paid parking at the upper lot',
      'Combine with dinner in west Sedona after'
    ],
    youtube: 'https://www.youtube.com/embed/H44Rb-GL4kM',
    youtubeTitle: 'Hiking Airport Mesa Loop — Sedona',
    links: [
      { label: 'AllTrails', url: 'https://www.alltrails.com/trail/us/arizona/airport-loop-trail' }
    ]
  },
  {
    id: 'brins-mesa',
    fromBasecamp: '19 mi · 35 min from basecamp',
    category: 'hike',
    name: 'Brins Mesa',
    short: 'Hike — Mesa top with backside loops',
    lat: 34.9006,
    lng: -111.7642,
    difficulty: 'Moderate',
    distance: '4.5 mi RT',
    description: `Climbs onto Brins Mesa for sweeping views of north Sedona and the Wilson Mountain massif. Can be looped with <strong>Soldier Pass on the back side</strong> for an 8-mile day that hits Devil's Kitchen, the pools, and the cave. Smart way to escape the front-side crowds while seeing the same landmarks.`,
    tips: [
      'Park at Jim Thompson TH (smaller, quieter than Soldier Pass)',
      'Loop with Soldier Pass for the full landmark tour',
      'Mostly exposed — start early'
    ],
    youtube: 'https://www.youtube.com/embed/cMT3H4_mXNc',
    youtubeTitle: 'Brins Mesa Trail Hike — Sedona, AZ [4K60]',
    links: [
      { label: 'AllTrails', url: 'https://www.alltrails.com/trail/us/arizona/brins-mesa-trail' }
    ]
  },
  {
    id: 'slide-rock',
    fromBasecamp: '28 mi · 50 min from basecamp',
    category: 'hike',
    name: 'Slide Rock State Park',
    short: 'Destination — Natural rock waterslides',
    lat: 34.9420,
    lng: -111.7530,
    difficulty: 'Easy',
    distance: 'Park grounds + short trails',
    description: `Iconic Oak Creek destination — a natural sandstone chute polished smooth into a series of waterslides through the orchards of an old apple homestead. Adjacent short trails (Pendley Homestead, Clifftop Nature Trail) for a leg-stretch. <strong>October is shoulder season</strong>: water will be cold and crowds way thinner than summer, but the orchards are picking and the foliage is at peak. Bring grippy water shoes — that slickrock is no joke.`,
    tips: [
      '$20-30/vehicle entry depending on season',
      'Drive: ~30 min north up Oak Creek Canyon (Hwy 89A)',
      'Water is COLD in October — fine for a quick send, not a long swim',
      'Pair with West Fork (5 min further north) for a full canyon day',
      'Apple-picking happens late Sep through late Oct'
    ],
    youtube: 'https://www.youtube.com/embed/QoyjbfeMhTo',
    youtubeTitle: 'Slide Rock, Sedona, Arizona [4K]',
    links: [
      { label: 'AZ State Parks: Slide Rock', url: 'https://azstateparks.com/slide-rock' },
      { label: 'Park Map & Hours', url: 'https://azstateparks.com/slide-rock/explore/maps' }
    ]
  },
  {
    id: 'loy-canyon',
    fromBasecamp: '~3 mi · 8 min from basecamp (closest hike on the map)',
    category: 'hike',
    name: 'Loy Canyon Trail',
    short: 'Hike — Red-walled canyon floor + scramble option',
    lat: 34.9322,
    lng: -111.9250,
    difficulty: 'Easy-Moderate (Hard if going to the saddle)',
    distance: '5-7 mi RT typical · 11.8 mi RT full to Secret Mountain saddle',
    description: `<strong>Sleeper pick literally next to basecamp.</strong> Long red-walled canyon floor with vermilion and buff sandstone cliffs pressing in, dry streambed with flash-flood-sculpted rock features. Most parties do 5-7 mi RT and turn around before the upper headwall. If you push to the top, the final 3 mi is a <strong>genuine Class 3 hand-and-foot scramble</strong> up to Secret Mountain saddle — the most sustained scramble of any hike within an hour of basecamp.`,
    tips: [
      'Dry streambed — no water-crossing concerns in October',
      'Start early — the upper south-facing section gets warm',
      'Most do a 5-7 mi RT and turn around; pushing to the saddle adds real elevation + Class 3 scramble',
      'Trailhead at Hancock Ranch end of Loy Butte Rd — very close to camp'
    ],
    youtube: null,
    links: [
      { label: 'USFS Coconino: Loy Canyon #5', url: 'https://www.fs.usda.gov/r03/coconino/recreation/trails/loy-canyon-trail-no-5' },
      { label: 'Arizona Highways: Loy Canyon', url: 'https://www.arizonahighways.com/loy-canyon-trail' }
    ]
  },
  {
    id: 'secret-canyon',
    fromBasecamp: '~10 mi · 30-40 min from basecamp (FR 152 last 3.4 mi is slow HC dirt)',
    category: 'hike',
    name: 'Secret Canyon + HS Canyon',
    short: 'Hike — Slottiest hike in the Dry Creek drainage',
    lat: 34.9302,
    lng: -111.8067,
    difficulty: 'Moderate (route-finding deeper in)',
    distance: '5-8 mi RT typical · 4.4+ mi one-way to upper canyon',
    description: `<strong>The slottiest "trail" hike near Sedona.</strong> Permanent small stream, pools, boulder-filled narrow channels with short scrambles to bypass dryfalls, red walls closing in. <strong>HS Canyon branches left at 0.7 mi</strong> and climbs toward Maroon Mountain's sheer cliffs — quieter, often-empty side canyon. Combining the two = the best sleeper day in the Dry Creek drainage.`,
    tips: [
      '⚠️ FR 152 needs high-clearance 4WD for the last 3.4 mi — budget 30 min of slow crawling each way',
      'Stream is small and cool but crossable in shoes — not a wade hike',
      '⚠️ Avoid if any rain in the forecast (flash-flood terrain)',
      'Branch left at 0.7 mi for the HS Canyon spur — quieter than the main fork'
    ],
    youtube: null,
    links: [
      { label: 'Secret Canyon #121 — AmericanSouthwest', url: 'https://www.americansouthwest.net/arizona/sedona/secret_canyon.html' },
      { label: 'AllTrails: HS and Secret Canyons', url: 'https://www.alltrails.com/trail/us/arizona/hs-and-secret-canyons' }
    ]
  }

  // FRIENDS & FAMILY PICKS
  // Add entries here when someone actually suggests something. For pins
  // already on the map, just add `suggested: true` (and optionally
  // `suggestedBy: 'name'`) to that pin and it'll get a gold star badge.
  // For new spots, add a pin with `category: 'suggested'`.

  // MY FAVORITES
  // Personal favorites are flagged with `favorite: true` on any existing
  // pin. They get a red heart badge on the map and in the list view —
  // separate from the gold star (friends & family) so you can tell who
  // recommended what.

  // PERSONAL NOTES
  // Add `note: 'free text'` to any pin to attach a personal observation
  // that's not a "favorite" flag. Notes show as a yellow sticky-note
  // call-out in the popup, modal, and list view. Useful for opinions
  // like "looks easy but might be a good warmup" — separate from the
  // editorial `tips` array (which is general field advice).

  // DANGER / SKULL & CROSSBONES
  // Add `danger: true` to any pin to put a black skull badge on the
  // map pin and a "USE EXTREME CAUTION" warning in the popup and modal.
  // Use for trails with real consequences (cliff exposure, no bailout,
  // expert-only).
];

const CATEGORIES = {
  basecamp:  { label: 'Basecamp', color: '#d97706', icon: '⛺' },
  shop:      { label: 'Bike Shop', color: '#0891b2', icon: '🔧' },
  mtb:       { label: 'Mountain Bike', color: '#dc2626', icon: '🚵' },
  ohv:       { label: 'E-Dirt Bike (OHV)', color: '#ea580c', icon: '🏍️' },
  hike:      { label: 'Hike', color: '#16a34a', icon: '🥾' },
  suggested: { label: 'Friends & Family Picks', color: '#eab308', icon: '★' }
};
