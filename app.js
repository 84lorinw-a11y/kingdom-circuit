"use strict";

console.info("Kingdom Circuit production multipage build loaded");
const BASE = "/";
const LIVE_EVENTS_URL = `${BASE}events.json`;
const LIVE_ARTISTS_URL = `${BASE}config/artists.json`;
const SITE_BUILD = "production-v2-verified-artist-images-icons";
const SUPPLEMENTAL_EVENTS_URL = `${BASE}supplemental-events.json?v=2`;
const RUN_STATUS_URL = `${BASE}run-status.json`;
const FALLBACK_EVENT_IMAGE = `${BASE}assets/event-fallback.webp`;
const VERIFIED_ARTIST_IMAGE_ENDPOINT = "https://open.voidware.de/artist/";
const STATE_NAMES = {AL:"Alabama",AK:"Alaska",AZ:"Arizona",AR:"Arkansas",CA:"California",CO:"Colorado",CT:"Connecticut",DE:"Delaware",DC:"District of Columbia",FL:"Florida",GA:"Georgia",HI:"Hawaii",ID:"Idaho",IL:"Illinois",IN:"Indiana",IA:"Iowa",KS:"Kansas",KY:"Kentucky",LA:"Louisiana",ME:"Maine",MD:"Maryland",MA:"Massachusetts",MI:"Michigan",MN:"Minnesota",MS:"Mississippi",MO:"Missouri",MT:"Montana",NE:"Nebraska",NV:"Nevada",NH:"New Hampshire",NJ:"New Jersey",NM:"New Mexico",NY:"New York",NC:"North Carolina",ND:"North Dakota",OH:"Ohio",OK:"Oklahoma",OR:"Oregon",PA:"Pennsylvania",RI:"Rhode Island",SC:"South Carolina",SD:"South Dakota",TN:"Tennessee",TX:"Texas",UT:"Utah",VT:"Vermont",VA:"Virginia",WA:"Washington",WV:"West Virginia",WI:"Wisconsin",WY:"Wyoming"};
// Artist source registry imported from Book4.xlsx. Only rows marked Verified are enriched.
const ARTIST_ROSTER_ORDER = [
  "Lecrae",
  "Hulvey",
  "KB",
  "Caleb Gordon",
  "Andy Mineo",
  "nobigdyl.",
  "1K Phew",
  "Miles Minnick",
  "Jon Keith",
  "Tedashii",
  "Trip Lee",
  "FLAME",
  "Scootie Wop",
  "Aaron Cole",
  "WHATUPRG",
  "Anike",
  "Limoblaze",
  "Jackie Hill Perry",
  "Social Club Misfits",
  "Steven Malcolm",
  "GAWVI",
  "EGR",
  "Mike Malagies",
  "Fern",
  "Marty",
  "BrvndonP",
  "Skema Boy",
  "Madison Ryann Ward",
  "Zauntee",
  "Bizzle",
  "Derek Minor",
  "Canon",
  "Parris Chariz",
  "Aklesso",
  "Tommy Zuko",
  "Sevin",
  "Da' T.R.U.T.H.",
  "Wordsplayed",
  "Forrest Frank",
  "Alex Jean",
  "gio.",
  "Torey D'Shaun",
  "Redimi2",
  "GRITS",
  "Funky",
  "NF",
  "Nic D",
  "Manafest",
  "Pastor Mike Jr.",
  "Pregador Luo",
  "Nesk Only",
  "Futuristic",
  "Beacon Light",
  "Sondae",
  "Dee-1",
  "Kieran the Light",
  "Childlike CiCi",
  "Yung Kriss",
  "Eluzai",
  "tylerhateslife",
  "S.B.G.",
  "Aha Gazelle",
  "EmanuelDaProphet",
  "Mike Teezy",
  "Porsha Love",
  "Reece Lache'",
  "LaNell Grant",
  "Red Tips",
  "Dell Mac",
  "indie tribe.",
  "DJ Mykael V",
  "Mogli the Iceburg",
  "Tommy Royale",
  "Jay-Way",
  "Ty Brasel",
  "J. Monty",
  "Datin",
  "Jered Sanders",
  "A.I. The Anomaly",
  "Selah the Corner",
  "Bumps INF",
  "Bryann T",
  "Young Bro",
  "KJ-52",
  "Nicky Gracious",
  "ASAP Preach",
  "Eshon Burgundy",
  "Sho Baraka",
  "Propaganda",
  "Shai Linne",
  "Thi'sl",
  "Swoope",
  "Ruslan",
  "Mission",
  "DaeShawn Forrest",
  "BigBreeze",
  "C4 Crotona",
  "Alexxander",
  "2819 Worship",
  "George.Rose",
  "Kijan Boone",
  "Jude Barclay",
  "Kaleb Mitchell",
  "Xay Hill",
  "DKG Kie",
  "J. Crum",
  "Nathan Davis Jr.",
  "Angie Rose",
  "Aasha Marie",
  "R-Swift",
  "No Malice",
  "DC3",
  "Don Ready",
  "Not Klyde",
  "404 Chew",
  "Alphein",
  "Bill B.",
  "G3rm 43",
  "GiNŌSKŌ",
  "Glenn Ray",
  "I.A.N.",
  "IDEGO",
  "Isreal Perez",
  "J J L",
  "Jacob Beard",
  "JWoodz",
  "Kaden Jordan",
  "MAYIA",
  "Megan Tossi",
  "mica",
  "Myles Maestro",
  "Nat Lauren",
  "Peair",
  "Razzie",
  "Saint Jones",
  "Stixx aka Conejo",
  "Tay Stunna",
  "YakiTheKid",
  "yumiya!",
  "Vic Lucas",
  "Kevi Morse",
  "Chris Caro",
  "EJ Swavv",
  "Kelo",
  "J.Solo",
  "Tds Cam",
  "Kham",
  "WHEREISDAVINCI",
  "Tukool Tiff",
  "Tylynn",
  "De'Aris",
  "Will Kellum",
  "Jonah Daniel",
  "outr.cty",
  "B. Cooper",
  "YP aka Young Paul",
  "Untidld",
  "DEON",
  "Jamil",
  "Kvng Flvcko",
  "Y Shadey",
  "MotionPlus",
  "Dante' Pride",
  "Adriel Cruz",
  "Drea LP",
  "Solachi Voz",
  "Jeannie Ortega",
  "A Mose",
  "Arielle Nichole",
  "Jekasole",
  "Heesun Lee",
  "Mahogany Jones",
  "Linga TheBoss",
  "Latoria",
  "Shy Speaks",
  "Serious Voice",
  "Tarcea Renee",
  "4eva",
  "Ada Betsabé",
  "BreeKay & Kasairi",
  "Bri Smilez",
  "Butta P",
  "Carita Cole",
  "Cass",
  "Dice Gamble",
  "Keiana",
  "Licy Be",
  "Pristavia",
  "Erica Mason",
  "Kay Sade",
  "Jackie Legere",
  "Foure",
  "Chozenn",
  "V. Rose",
  "Mike REAL",
  "Spec",
  "Christon Gray",
  "Dre Murray",
  "S.O.",
  "Reconcile",
  "Corey Paul",
  "Alex Faith",
  "Tony Tillman",
  "Chad Jones",
  "Dillon Chase",
  "Json",
  "J.R.",
  "Stephen the Levite",
  "Timothy Brindle",
  "Hazakim",
  "Evangel",
  "God's Servant",
  "Beautiful Eulogy",
  "Braille",
  "116",
  "350",
  "Battz",
  "Byron Juane",
  "Coby James",
  "De La Cruz",
  "Gavin the HotRod",
  "Hollyn",
  "JGivens",
  "Kings Kaleidoscope",
  "Odd Thomas",
  "Q-Flo",
  "Rare of Breed",
  "Ryan Trey",
  "Swaizy",
  "The Weathrman",
  "Toschii",
  "Trendsetter Sense",
  "Brother Bo",
  "Tommy Chapa",
  "B. Cody Shields",
  "Santana Rose",
  "DJ Winn",
  "J.List",
  "BIG HOLY",
  "D-Maub",
  "K-Drama",
  "Monster Tarver",
  "Taelor Gray",
  "ZEE",
  "IMRSQD",
  "TJ Carroll",
  "Coop",
  "CJ Emulous",
  "Lul DreDay",
  "REDEEMED",
  "Pishko",
  "Paul Russell",
  "MC Jin",
  "Gemstones",
  "Mouthpi3ce",
  "John Givez",
  "Beleaf",
  "J. Han",
  "Sam Ock",
  "Dream Junkies",
  "Jet Trouble",
  "Skrip",
  "Deraj",
  "Surf Gvng",
  "Ki'Shon Furlow",
  "Dru Bex",
  "Brinson",
  "Canton Jones",
  "Mr. Del",
  "Pettidee",
  "Fresh IE",
  "Applejaxx",
  "Fedel",
  "Antwoine Hill",
  "Brandon Trejo",
  "Monica Hill Trejo",
  "Moe Grant",
  "Isaiah Robin",
  "Guvna B",
  "Faith Child",
  "Still Shadey",
  "Feed'Em",
  "Reblah",
  "Triple O",
  "A Star",
  "J Vessel",
  "Dwayne Tryumf",
  "Manny Montes",
  "Alex Zurdo",
  "Musiko",
  "Indiomar",
  "Gabriel EMC",
  "Jay Kalyl",
  "Niko Eme",
  "Lizzy Parra",
  "Rubinsky RBK",
  "Madiel Lara",
  "Ariel Kelly",
  "Oba Reengy"
];
const VERIFIED_ARTIST_REGISTRY = {
  "lecrae": {
    "aliases": [
      "Lecrae"
    ],
    "website": "https://lecrae.com",
    "instagramProfile": "https://www.instagram.com/lecrae/",
    "spotifyProfile": "https://open.spotify.com/artist/1CFCsEqKrCyvAFKOATQHiW",
    "youtubeProfile": "https://www.youtube.com/@lecraeofficial",
    "officialImageSource": "https://lecrae.com",
    "sourceRegistryVerified": true
  },
  "hulvey": {
    "aliases": [
      "Hulvey"
    ],
    "website": "https://hulvey.com",
    "instagramProfile": "https://www.instagram.com/hulvey/",
    "spotifyProfile": "https://open.spotify.com/artist/3zSrc5vUlUxyDdS0KrxFJO",
    "youtubeProfile": "https://www.youtube.com/@hulvey",
    "officialImageSource": "https://hulvey.com",
    "sourceRegistryVerified": true
  },
  "kb": {
    "aliases": [
      "KB"
    ],
    "website": "https://www.whoiskb.com",
    "instagramProfile": "https://www.instagram.com/kb_hga/",
    "spotifyProfile": "https://open.spotify.com/artist/77IKXFvO7SpWrq8hflrUXc",
    "youtubeProfile": "https://www.youtube.com/@KB_HGA",
    "officialImageSource": "https://www.whoiskb.com",
    "sourceRegistryVerified": true
  },
  "caleb gordon": {
    "aliases": [
      "Caleb Gordon"
    ],
    "website": "https://tprlive.co/collections/caleb-gordon-the-eden-experience",
    "instagramProfile": "https://www.instagram.com/calebfromeden",
    "spotifyProfile": "https://open.spotify.com/artist/6s3XaJkcT7464G4oII9V41",
    "youtubeProfile": "https://www.youtube.com/@CalebGordon",
    "officialImageSource": "https://tprlive.co/collections/caleb-gordon-the-eden-experience",
    "sourceRegistryVerified": true
  },
  "andy mineo": {
    "aliases": [
      "Andy Mineo"
    ],
    "website": "https://andymineo.com",
    "instagramProfile": "https://www.instagram.com/andymineo/",
    "spotifyProfile": "https://open.spotify.com/artist/1TMrnxBwZfmfRxsGzkNIHw",
    "youtubeProfile": "https://www.youtube.com/@AndyMineo",
    "officialImageSource": "https://andymineo.com",
    "sourceRegistryVerified": true
  },
  "nobigdyl.": {
    "aliases": [
      "nobigdyl.",
      "nobigdyl"
    ],
    "website": "https://www.dyllie.com/",
    "instagramProfile": "https://www.instagram.com/nobigdyl/",
    "spotifyProfile": "https://open.spotify.com/artist/2d8NsBa8O4C6bgQatFP5V4",
    "youtubeProfile": "https://www.youtube.com/@nobigdyl.official",
    "officialImageSource": "https://www.instagram.com/nobigdyl/",
    "sourceRegistryVerified": true
  },
  "1k phew": {
    "aliases": [
      "1K Phew",
      "1K PHEW",
      "1KPhew"
    ],
    "website": "https://www.1kphew.com/",
    "instagramProfile": "https://www.instagram.com/1kphew/",
    "spotifyProfile": "https://open.spotify.com/artist/6CQGrt3AJ2gx5oMSR0mwbl",
    "youtubeProfile": "https://www.youtube.com/@Phewskii",
    "officialImageSource": "https://www.1kphew.com/bio",
    "sourceRegistryVerified": true
  },
  "miles minnick": {
    "aliases": [
      "Miles Minnick"
    ],
    "website": "https://milesminnick.com/",
    "instagramProfile": "https://www.instagram.com/miles.minnick/",
    "spotifyProfile": "https://open.spotify.com/artist/1VEtrxO5KlDXfYGKBI6Ldr",
    "youtubeProfile": "https://www.youtube.com/@MilesMinnick",
    "officialImageSource": "https://milesminnick.com/",
    "sourceRegistryVerified": true
  },
  "jon keith": {
    "aliases": [
      "Jon Keith"
    ],
    "website": "https://alienzalive.com/artist/jon-keith/",
    "instagramProfile": "https://www.instagram.com/jonkeith/",
    "spotifyProfile": "https://open.spotify.com/artist/0PUc1lwaZpPJaMr0v4Gdvo",
    "youtubeProfile": "https://www.youtube.com/@JonKeith",
    "officialImageSource": "https://open.spotify.com/artist/0PUc1lwaZpPJaMr0v4Gdvo",
    "sourceRegistryVerified": true
  },
  "tedashii": {
    "aliases": [
      "Tedashii"
    ],
    "website": "https://www.reachrecords.com/artists/tedashii/",
    "instagramProfile": "https://www.instagram.com/tedashii/",
    "spotifyProfile": "https://open.spotify.com/artist/4c6lhwoOrmgNWvl0GxHlW1",
    "youtubeProfile": "https://www.youtube.com/@tedashii_116",
    "officialImageSource": "https://www.reachrecords.com/artists/tedashii/",
    "sourceRegistryVerified": true
  },
  "trip lee": {
    "aliases": [
      "Trip Lee"
    ],
    "website": "https://builttobrag.com/",
    "instagramProfile": "https://www.instagram.com/triplee/",
    "spotifyProfile": "https://open.spotify.com/artist/12H1Dmi64fAmmARrsyVFzy",
    "youtubeProfile": "https://www.youtube.com/@triplee_116",
    "officialImageSource": "https://builttobrag.com/",
    "sourceRegistryVerified": true
  },
  "flame": {
    "aliases": [
      "FLAME",
      "Flame"
    ],
    "website": "https://www.instagram.com/flame314/",
    "instagramProfile": "https://www.instagram.com/flame314/",
    "spotifyProfile": "https://open.spotify.com/artist/2s6kyMmJZFgPCHXU0QxJLp",
    "youtubeProfile": "https://www.youtube.com/@ClearSightMusic",
    "officialImageSource": "https://www.instagram.com/flame314/",
    "sourceRegistryVerified": true
  },
  "scootie wop": {
    "aliases": [
      "Scootie Wop"
    ],
    "website": "https://starrbaby.com/",
    "instagramProfile": "https://www.instagram.com/scootiewop/",
    "spotifyProfile": "https://open.spotify.com/artist/1JAoqu34UmPWUUAjLMXt5I",
    "youtubeProfile": "https://www.youtube.com/channel/UCxiuNRFW37J9uXL6SGCW0MQ",
    "officialImageSource": "https://starrbaby.com/",
    "sourceRegistryVerified": true
  },
  "aaron cole": {
    "aliases": [
      "Aaron Cole"
    ],
    "website": "https://www.iamaaroncole.com/",
    "instagramProfile": "https://www.instagram.com/iamaaroncole/",
    "spotifyProfile": "https://open.spotify.com/artist/0OQ8y7heASb1vEX5WXvjCr",
    "youtubeProfile": "https://www.youtube.com/channel/UCFV59kjh9BTGJGYwfrQ247Q",
    "officialImageSource": "https://www.iamaaroncole.com/",
    "sourceRegistryVerified": true
  },
  "whatuprg": {
    "aliases": [
      "WHATUPRG",
      "WHATUPRG?"
    ],
    "website": "https://www.reachrecords.com/artists/whatuprg/",
    "instagramProfile": "https://www.instagram.com/whatuprg/",
    "spotifyProfile": "https://open.spotify.com/artist/6YgYm3f9ifsz4OwQt8jql7",
    "youtubeProfile": "https://www.youtube.com/@WHATUPRG",
    "officialImageSource": "https://www.reachrecords.com/artists/whatuprg/",
    "sourceRegistryVerified": true
  },
  "anike": {
    "aliases": [
      "Anike",
      "Wande"
    ],
    "website": "https://anike.net/",
    "instagramProfile": "https://www.instagram.com/anike/",
    "spotifyProfile": "https://open.spotify.com/artist/0GdzQJqgRL5SHp7kXOKba0",
    "youtubeProfile": "https://www.youtube.com/c/wandeisola",
    "officialImageSource": "https://anike.net/",
    "sourceRegistryVerified": true
  },
  "limoblaze": {
    "aliases": [
      "Limoblaze"
    ],
    "website": "https://www.limoblaze.com/",
    "instagramProfile": "https://www.instagram.com/limoblaze_/",
    "spotifyProfile": "https://open.spotify.com/artist/0liXA3xwx6pncxYQA30ahT",
    "youtubeProfile": "https://www.youtube.com/@limoblaze",
    "officialImageSource": "https://www.limoblaze.com/",
    "sourceRegistryVerified": true
  },
  "jackie hill perry": {
    "aliases": [
      "Jackie Hill Perry",
      "Jackie Hill-Perry"
    ],
    "website": "https://www.jackiehillperry.com/",
    "instagramProfile": "https://www.instagram.com/jackiehillperry/",
    "spotifyProfile": "https://open.spotify.com/artist/0Lf9qKpKwy6fJtfM7UWLV0",
    "youtubeProfile": "https://www.youtube.com/@jackiehillperrychannel",
    "officialImageSource": "https://www.jackiehillperry.com/",
    "sourceRegistryVerified": true
  },
  "social club misfits": {
    "aliases": [
      "Social Club Misfits",
      "Social Club"
    ],
    "website": "https://socialclubmisfits.com/",
    "instagramProfile": "https://www.instagram.com/socialclubmisfits/",
    "spotifyProfile": "https://open.spotify.com/artist/0wnsM0ziqToBwQeEbH0akL",
    "youtubeProfile": "https://www.youtube.com/@socialclubmisfits",
    "officialImageSource": "https://socialclubmisfits.com/",
    "sourceRegistryVerified": true
  },
  "steven malcolm": {
    "aliases": [
      "Steven Malcolm"
    ],
    "website": "https://stevenmalcolm.com/",
    "instagramProfile": "https://www.instagram.com/stevenmalcolmmusic/",
    "spotifyProfile": "https://open.spotify.com/artist/5yqWHaDl8ZrYgeKANLyIv8",
    "youtubeProfile": "https://www.youtube.com/c/StevenMalcolm",
    "officialImageSource": "https://stevenmalcolm.com/",
    "sourceRegistryVerified": true
  },
  "gawvi": {
    "aliases": [
      "GAWVI",
      "Gawvi"
    ],
    "website": "https://www.gawvi.co/",
    "instagramProfile": "https://www.instagram.com/gawvi/",
    "spotifyProfile": "https://open.spotify.com/artist/0oPd8f0W82Tgrazx2PYNab",
    "youtubeProfile": "https://www.youtube.com/@GAWVI",
    "officialImageSource": "https://www.gawvi.co/",
    "sourceRegistryVerified": true
  },
  "egr": {
    "aliases": [
      "EGR",
      "EGR MUZIK",
      "EGRxOFFICIAL"
    ],
    "website": "https://www.youtube.com/@EGRxOFFICIAL",
    "instagramProfile": "https://www.instagram.com/egrxofficial/",
    "spotifyProfile": "https://open.spotify.com/artist/4EJIkbig1thbV3C3B68c56",
    "youtubeProfile": "https://www.youtube.com/@EGRxOFFICIAL",
    "officialImageSource": "https://www.youtube.com/@EGRxOFFICIAL",
    "sourceRegistryVerified": true
  },
  "mike malagies": {
    "aliases": [
      "Mike Malagies"
    ],
    "website": "https://www.mikemalagiesofficial.com/",
    "instagramProfile": "https://www.instagram.com/mikemalagies/",
    "spotifyProfile": "https://open.spotify.com/artist/6Ms95MzjHZvqs79Nw3hXrx",
    "youtubeProfile": "https://www.youtube.com/channel/UCLbkU1IRos-VlB7fwACr_YQ",
    "officialImageSource": "https://www.mikemalagiesofficial.com/",
    "sourceRegistryVerified": true
  },
  "fern": {
    "aliases": [
      "Fern",
      "Fern of Social Club Misfits"
    ],
    "website": "https://fernofficial.com/",
    "instagramProfile": "https://www.instagram.com/fernie_sc/",
    "spotifyProfile": "https://open.spotify.com/artist/0aDl6JJeQf1eZ35ymzirwp",
    "youtubeProfile": "https://www.youtube.com/channel/UCjB6amZ5v-e6H8lK2HerjmQ",
    "officialImageSource": "https://fernofficial.com/",
    "sourceRegistryVerified": true
  },
  "marty": {
    "aliases": [
      "Marty",
      "Marty of Social Club Misfits",
      "Marty Mar"
    ],
    "website": "https://www.instagram.com/deathbymartymar/?hl=en",
    "instagramProfile": "https://www.instagram.com/deathbymartymar/",
    "spotifyProfile": "https://open.spotify.com/artist/5BfKKSmpGmj2moMNlaWeJK",
    "youtubeProfile": "https://www.youtube.com/@deathbymartymar",
    "officialImageSource": "https://www.instagram.com/deathbymartymar/?hl=en",
    "sourceRegistryVerified": true
  },
  "brvndonp": {
    "aliases": [
      "BrvndonP",
      "Brvndon P"
    ],
    "website": "https://iambrvndonp.com/",
    "instagramProfile": "https://www.instagram.com/iambrvndonp/",
    "spotifyProfile": "https://open.spotify.com/artist/0hO40pJ3oZNnq7joT2xQGy",
    "youtubeProfile": "https://www.youtube.com/@BRVNDONP",
    "officialImageSource": "https://iambrvndonp.com/",
    "sourceRegistryVerified": true
  },
  "skema boy": {
    "aliases": [
      "Skema Boy"
    ],
    "website": "https://rixonentertainment.com/skema-boy",
    "instagramProfile": "https://www.instagram.com/skema.boy/",
    "spotifyProfile": "https://open.spotify.com/artist/1KTljUXZGt7HkAFFEnDBn1",
    "youtubeProfile": "https://www.youtube.com/@skemaboy",
    "officialImageSource": "https://rixonentertainment.com/skema-boy",
    "sourceRegistryVerified": true
  },
  "madison ryann ward": {
    "aliases": [
      "Madison Ryann Ward"
    ],
    "website": "https://madisonryannward.com/",
    "instagramProfile": "https://www.instagram.com/madisonryannward/",
    "spotifyProfile": "https://open.spotify.com/artist/6eAUAR4N9NOpirukqdIzVI",
    "youtubeProfile": "https://www.youtube.com/@madisonryannward9730",
    "officialImageSource": "https://madisonryannward.com/",
    "sourceRegistryVerified": true
  },
  "zauntee": {
    "aliases": [
      "Zauntee"
    ],
    "website": "https://www.zauntee.com/",
    "instagramProfile": "https://www.instagram.com/zauntee/",
    "spotifyProfile": "https://open.spotify.com/artist/7jyr9Co4MKL1iWML1G7vch",
    "youtubeProfile": "https://www.youtube.com/@zauntee",
    "officialImageSource": "https://www.zauntee.com/",
    "sourceRegistryVerified": true
  },
  "bizzle": {
    "aliases": [
      "Bizzle"
    ],
    "website": "https://bizzle.vip/",
    "instagramProfile": "https://www.instagram.com/bizzle/",
    "spotifyProfile": "https://open.spotify.com/artist/0P8V2XSw1mIo8739T1qjzr",
    "youtubeProfile": "https://www.youtube.com/user/playbizzle21",
    "officialImageSource": "https://bizzle.vip/",
    "sourceRegistryVerified": true
  },
  "derek minor": {
    "aliases": [
      "Derek Minor"
    ],
    "website": "https://derekminor.com/",
    "instagramProfile": "https://www.instagram.com/thederekminor/",
    "spotifyProfile": "https://open.spotify.com/artist/3fn8lZLy7Q61AXCWWPYC4B",
    "youtubeProfile": "https://www.youtube.com/@derekminor",
    "officialImageSource": "https://derekminor.com/",
    "sourceRegistryVerified": true
  },
  "canon": {
    "aliases": [
      "Canon"
    ],
    "website": "https://www.getthecanon.com/",
    "instagramProfile": "https://www.instagram.com/getthecanon/",
    "spotifyProfile": "https://open.spotify.com/artist/1dIjbaW9JTTQQ7ufrQnGsq",
    "youtubeProfile": "https://www.youtube.com/@getthecanon",
    "officialImageSource": "https://www.getthecanon.com/",
    "sourceRegistryVerified": true
  },
  "parris chariz": {
    "aliases": [
      "Parris Chariz"
    ],
    "website": "https://www.instagram.com/parrischariz/?hl=en",
    "instagramProfile": "https://www.instagram.com/parrischariz/",
    "spotifyProfile": "https://open.spotify.com/artist/2Vt6gyhUH7Vj2cybfQWOqM",
    "youtubeProfile": "https://www.youtube.com/@parrischariz",
    "officialImageSource": "https://www.instagram.com/parrischariz/?hl=en",
    "sourceRegistryVerified": true
  },
  "aklesso": {
    "aliases": [
      "Aklesso"
    ],
    "website": "https://www.aklesso.com/",
    "instagramProfile": "https://www.instagram.com/aklesso/",
    "spotifyProfile": "https://open.spotify.com/artist/7r3HxO330lmabOprT2MMFK",
    "youtubeProfile": "https://www.youtube.com/@aklesso",
    "officialImageSource": "https://www.aklesso.com/",
    "sourceRegistryVerified": true
  },
  "tommy zuko": {
    "aliases": [
      "Tommy Zuko"
    ],
    "website": "https://www.tommyzuko.com/",
    "instagramProfile": "https://www.instagram.com/tommyzuko/",
    "spotifyProfile": "https://open.spotify.com/artist/6GEZnFo9mFSItpAWzswBpT",
    "youtubeProfile": "https://www.youtube.com/@TommyZuko",
    "officialImageSource": "https://www.tommyzuko.com/",
    "sourceRegistryVerified": true
  },
  "sevin": {
    "aliases": [
      "Sevin",
      "Sevin Duce",
      "Sevin HOG MOB",
      "HOG MOB Ministries",
      "HOG MOB"
    ],
    "website": "https://hogmob.com/sevin/",
    "instagramProfile": "https://www.instagram.com/sevinhogmob/",
    "spotifyProfile": "https://open.spotify.com/artist/1I402d4s0Xe8EntQI3u96l",
    "youtubeProfile": "https://www.youtube.com/@HOGMOBSEVIN",
    "officialImageSource": "https://hogmob.com/sevin/",
    "sourceRegistryVerified": true
  },
  "da' t.r.u.t.h.": {
    "aliases": [
      "Da' T.R.U.T.H.",
      "Da Truth",
      "Da T.R.U.T.H."
    ],
    "website": "https://www.instagram.com/datruthonduty/?hl=en",
    "instagramProfile": "https://www.instagram.com/datruthonduty/",
    "spotifyProfile": "https://open.spotify.com/artist/2ISIE0MEDMdAF2LDMLrVD4",
    "youtubeProfile": "https://www.youtube.com/channel/UCnJCP07fWQ5BIFd7toUnxKg",
    "officialImageSource": "https://www.instagram.com/datruthonduty/?hl=en",
    "sourceRegistryVerified": true
  },
  "wordsplayed": {
    "aliases": [
      "Wordsplayed",
      "Wordsplayed.",
      "Wordsplayed?"
    ],
    "website": "https://wordsplayed.neocities.org/",
    "instagramProfile": "https://www.instagram.com/wordsplayed/",
    "spotifyProfile": "https://open.spotify.com/artist/0AKzJfX9rdEu8WOqeBLEaO",
    "youtubeProfile": "https://music.youtube.com/@wordsplayedworldwide",
    "officialImageSource": "https://wordsplayed.neocities.org/",
    "sourceRegistryVerified": true
  },
  "forrest frank": {
    "aliases": [
      "Forrest Frank"
    ],
    "website": "https://forrestfrank.com/",
    "instagramProfile": "https://www.instagram.com/hiforrest/",
    "spotifyProfile": "https://open.spotify.com/artist/1scVfBymTr3CeZ4imMj1QJ",
    "youtubeProfile": "https://www.youtube.com/@hiforrest",
    "officialImageSource": "https://forrestfrank.com/",
    "sourceRegistryVerified": true
  }
};
const ARTIST_OVERRIDES = {
  "kb": {
    spotifyProfile: "https://open.spotify.com/artist/77IKXFvO7SpWrq8hflrUXc"
  },
  "skema boy": {
    imageUrl: "assets/artists/skema-boy.webp",
    instagramProfile: "https://www.instagram.com/skema.boy/",
    spotifyProfile: "https://open.spotify.com/artist/1KTljUXZGt7HkAFFEnDBn1",
    youtubeProfile: "https://www.youtube.com/@skemaboy",
    officialProfile: "https://rixonentertainment.com/skema-boy"
  },
  "zauntee": {
    imageUrl: "assets/artists/zauntee.webp",
    imagePosition: "50% 32%",
    officialProfile: "https://zauntee.com/",
    instagramProfile: "https://www.instagram.com/zauntee/",
    youtubeProfile: "https://www.youtube.com/@zauntee"
  }
};
let EVENTS = [];
let ARTISTS = [];

const esc = value => String(value ?? "").replace(/[&<>'"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[ch]));
const normalize = value => String(value || "").trim().toLocaleLowerCase();
async function loadJson(primary, fallback) {
  try {
    const response = await fetch(primary, { cache: "no-store" });
    if (!response.ok) throw new Error(`${response.status}`);
    return await response.json();
  } catch (error) {
    console.warn(`Primary data unavailable; using ${fallback}`, error);
    const response = await fetch(`${BASE}${fallback}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Could not load ${fallback}`);
    return await response.json();
  }
}
async function loadOptionalJson(url) {
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) return [];
    const data = await response.json();
    return Array.isArray(data) ? data : [];
  } catch (error) {
    console.warn("Supplemental event data was unavailable.", error);
    return [];
  }
}

function spotifyArtistId(artist) {
  const value = artist?.spotifyProfile || (artist?.spotifyId ? `https://open.spotify.com/artist/${artist.spotifyId}` : "");
  const match = String(value).match(/open\.spotify\.com\/artist\/([A-Za-z0-9]+)/i);
  return match?.[1] || "";
}
function spotifyArtistImageUrl(artist) {
  if (artist?.sourceRegistryVerified !== true) return "";
  const spotifyId = spotifyArtistId(artist);
  return spotifyId ? `${VERIFIED_ARTIST_IMAGE_ENDPOINT}${encodeURIComponent(spotifyId)}` : "";
}
function verifiedArtistImageUrl(artist) {
  return artist?.imageUrl || spotifyArtistImageUrl(artist);
}
function applyArtistOverrides(artists) {
  const orderByName = new Map(ARTIST_ROSTER_ORDER.map((name, index) => [normalize(name), index + 1]));
  return artists.map(artist => {
    const key = normalize(artist.name);
    const legacyOverride = ARTIST_OVERRIDES[key] || {};
    const verifiedUpdate = VERIFIED_ARTIST_REGISTRY[key] || {};
    const rosterOrder = orderByName.get(key);
    const aliases = [...new Set([
      ...(artist.aliases || []),
      ...(legacyOverride.aliases || []),
      ...(verifiedUpdate.aliases || [])
    ])];
    const merged = {
      ...artist,
      ...legacyOverride,
      ...verifiedUpdate,
      ...(aliases.length ? { aliases } : {}),
      ...(rosterOrder ? { rosterOrder } : {})
    };
    const imageUrl = verifiedArtistImageUrl(merged);
    return imageUrl && !merged.imageUrl
      ? { ...merged, imageUrl, imageSource: "Verified Spotify artist profile" }
      : merged;
  });
}
function eventArtistSet(event) {
  return new Set((event.artists || []).map(normalize));
}
function sameEvent(existing, incoming) {
  if (!existing || !incoming || existing.startDate !== incoming.startDate) return false;
  if (normalize(existing.city) !== normalize(incoming.city)) return false;
  const sameVenue = normalize(existing.venue) && normalize(existing.venue) === normalize(incoming.venue);
  const existingArtists = eventArtistSet(existing);
  const sharedArtist = [...eventArtistSet(incoming)].some(name => existingArtists.has(name));
  return sameVenue || sharedArtist;
}
function shouldUseIncomingImage(existing, incoming) {
  if (!incoming.image) return false;
  if (incoming.imageOverride) return true;
  if (!existing.image) return true;
  const current = normalize(existing.image);
  return current === "assets/event-fallback.webp" || current.endsWith("/assets/event-fallback.webp") || existing.imageType === "fallback";
}
function mergeEventLists(primary, supplemental) {
  const merged = primary.map(event => ({ ...event, artists: [...(event.artists || [])] }));
  supplemental.forEach(incoming => {
    const existing = merged.find(event => sameEvent(event, incoming));
    if (!existing) {
      merged.push(incoming);
      return;
    }
    existing.artists = [...new Set([...(existing.artists || []), ...(incoming.artists || [])])];
    if (shouldUseIncomingImage(existing, incoming)) {
      existing.image = incoming.image;
      existing.imageType = incoming.imageType || existing.imageType;
      existing.imagePosition = incoming.imagePosition || existing.imagePosition;
    }
    if (!existing.firstSeen) existing.firstSeen = incoming.firstSeen;
  });
  return merged;
}
function localAssetUrl(value) {
  if (!value) return "";
  if (/^https?:\/\//i.test(value)) return value.replace(/^http:\/\//i, "https://");
  return `${BASE}${value.replace(/^\//, "")}`;
}

function artistConfig(name) {
  const target = normalize(name);
  return ARTISTS.find(artist => normalize(artist.name) === target || (artist.aliases || []).some(alias => normalize(alias) === target));
}
function eventImage(event) {
  const config = artistConfig(event.headliner || event.artists?.[0]);
  return localAssetUrl(event.image || config?.imageUrl) || FALLBACK_EVENT_IMAGE;
}

function imageClass(event) {
  return event.imageType === "event_artwork" ? "event-artwork" : "artist-photo";
}

function imagePosition(event) {
  return event.imagePosition || artistConfig(event.headliner)?.imagePosition || "center";
}
function parseLocalDate(value) {
  if (!value) return null;
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day, 12, 0, 0, 0);
}
function formatDate(event) {
  const date = parseLocalDate(event.startDate);
  if (!date) return "Date to be announced";
  let text = new Intl.DateTimeFormat("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric" }).format(date);
  if (event.startTime) {
    const [hour, minute] = event.startTime.split(":").map(Number);
    const time = new Date(2000, 0, 1, hour, minute || 0);
    text += ` - ${new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(time)}`;
  }
  return text;
}
function sourceText(event) {
  return event.sourceName || event.sources?.[0]?.name || "Official source";
}

function eventDetailUrl(event) {
  return `${BASE}event/?id=${encodeURIComponent(event.id)}`;
}

function artistProfileUrl(name) {
  return `${BASE}artists/profile/?name=${encodeURIComponent(name)}`;
}

function artistLinks(event) {
  return (event.artists || []).map(name => `<a href="${artistProfileUrl(name)}">${esc(name)}</a>`).join(" - ");
}
function isNew(event) {
  if (!event.firstSeen) return false;
  const seen = new Date(event.firstSeen);
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - 14);
  return seen >= cutoff;
}
function eventCard(event) {
  const search = [event.title, event.venue, event.city, event.state, event.sourceName, ...(event.artists || [])].join(" ").toLocaleLowerCase();
  const artists = (event.artists || []).map(normalize).join("|");
  const img = eventImage(event);
  const location = [event.city, event.state].filter(Boolean).join(", ") || "Location to be announced";
  const price = event.price ? `<p class="price-line">Listed price: ${esc(event.price)}</p>` : "";
  const recent = isNew(event) ? `<span class="badge">New to Kingdom Circuit</span>` : "";
  return `<article class="event-card" data-event-card data-search="${esc(search)}" data-artists="${esc(artists)}" data-state="${esc(event.state || "")}" data-type="${esc(event.eventType || "concert")}" data-date="${esc(event.startDate || "")}" data-end-date="${esc(event.endDate || event.startDate || "")}">
    <a class="event-media" href="${eventDetailUrl(event)}" aria-label="View ${esc(event.title)}"><img class="${imageClass(event)}" src="${esc(img)}" alt="${esc(event.title)} image" loading="lazy" style="object-position:${esc(imagePosition(event))}" onerror="this.onerror=null;this.className='event-artwork';this.src='${FALLBACK_EVENT_IMAGE}';"></a>
    <div class="event-content"><div class="event-main"><div class="event-badges"><span class="badge badge-gold">${esc(event.eventType === "festival" ? "Festival" : "Concert")}</span>${recent}</div><h3><a href="${eventDetailUrl(event)}">${esc(event.title)}</a></h3><p class="artist-line">${artistLinks(event)}</p><dl class="event-meta"><div><dt>Date</dt><dd>${esc(formatDate(event))}</dd></div><div><dt>Venue</dt><dd>${esc(event.venue || "Venue to be announced")}</dd></div><div><dt>Location</dt><dd>${esc(location)}</dd></div></dl>${price}</div><div class="event-footer"><a class="official-button" href="${esc(event.officialUrl || event.ticketUrl || "#")}" target="_blank" rel="noopener">Official details</a><p class="source-line">Source: ${esc(sourceText(event))}</p></div></div>
  </article>`;
}
function filterEvents(mode) {
  const today = new Date();
  if (mode === "festival") return EVENTS.filter(event => event.eventType === "festival");
  if (mode === "month") return EVENTS.filter(event => { const date = parseLocalDate(event.startDate); return date && date.getFullYear() === today.getFullYear() && date.getMonth() === today.getMonth(); });
  if (mode === "new") return EVENTS.filter(isNew);
  return EVENTS;
}
function fillSelect(select, values, labeler = value => value) {
  if (!select) return;
  const first = select.querySelector("option");
  select.innerHTML = first ? first.outerHTML : "";
  values.forEach(value => select.insertAdjacentHTML("beforeend", `<option value="${esc(value)}">${esc(labeler(value))}</option>`));
}

function startOfDay(value) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}
function dateMatchesMode(startDate, endDate, mode) {
  if (!mode || mode === "all") return true;
  const today = startOfDay(new Date());
  const start = parseLocalDate(startDate);
  const end = parseLocalDate(endDate) || start;
  if (!start || !end) return false;
  if (mode === "next30") { const last = new Date(today); last.setDate(last.getDate() + 30); return end >= today && start <= last; }
  if (mode === "month") return start.getFullYear() === today.getFullYear() && start.getMonth() === today.getMonth();
  if (mode === "weekend") { const friday = new Date(today); friday.setDate(friday.getDate() + ((5 - today.getDay() + 7) % 7)); const sunday = new Date(friday); sunday.setDate(sunday.getDate() + 2); return end >= friday && start <= sunday; }
  return true;
}
function setupEventFilters(cards) {
  const form = document.querySelector("[data-event-filters]");
  if (!form) return;
  const search = form.querySelector("[data-search-filter]");
  const artist = form.querySelector("[data-artist-filter]");
  const state = form.querySelector("[data-state-filter]");
  const type = form.querySelector("[data-type-filter]");
  const reset = form.querySelector("[data-reset-filters]");
  const count = document.querySelector("[data-results-count]");
  const empty = document.querySelector("[data-filtered-empty]");
  const chips = [...document.querySelectorAll(".filter-chip[data-date-mode],.filter-chip[data-type-mode]")];
  let dateMode = "all";
  const params = new URLSearchParams(location.search);
  if (params.get("artist") && artist) artist.value = normalize(params.get("artist"));
  if (params.get("state") && state) state.value = params.get("state").toUpperCase();
  function apply() {
    const needle = normalize(search?.value);
    const artistValue = artist?.value || "";
    const stateValue = state?.value || "";
    const typeValue = type?.value || "";
    let visible = 0;
    cards.forEach(card => {
      const names = (card.dataset.artists || "").split("|");
      const match = (!needle || (card.dataset.search || "").includes(needle)) && (!artistValue || names.includes(artistValue)) && (!stateValue || card.dataset.state === stateValue) && (!typeValue || card.dataset.type === typeValue) && dateMatchesMode(card.dataset.date, card.dataset.endDate, dateMode);
      card.hidden = !match;
      if (match) visible += 1;
    });
    if (count) count.textContent = `${visible} show${visible === 1 ? "" : "s"}`;
    if (empty) empty.hidden = visible !== 0;
  }
  [search, artist, state, type].forEach(control => control?.addEventListener(control === search ? "input" : "change", apply));
  chips.forEach(chip => chip.addEventListener("click", () => {
    if (chip.dataset.typeMode) { if (type) type.value = chip.dataset.typeMode; dateMode = "all"; }
    else { dateMode = chip.dataset.dateMode || "all"; if (type) type.value = ""; }
    chips.forEach(item => item.classList.remove("active"));
    chip.classList.add("active");
    apply();
  }));
  reset?.addEventListener("click", () => { form.reset(); dateMode = "all"; chips.forEach(item => item.classList.toggle("active", item.dataset.dateMode === "all")); apply(); });
  apply();
}
function renderEventList() {
  const grid = document.querySelector("[data-event-grid]");
  if (!grid) return;
  const mode = document.querySelector("[data-event-list-mode]")?.dataset.eventListMode || "all";
  const list = filterEvents(mode).sort((a, b) => (a.startDate || "").localeCompare(b.startDate || "") || (a.startTime || "").localeCompare(b.startTime || ""));
  grid.innerHTML = list.map(eventCard).join("");
  document.querySelector("[data-loading-panel]")?.remove();
  const artistValues = [...new Set(list.flatMap(event => event.artists || []).map(normalize))].sort();
  const displayByNorm = new Map(list.flatMap(event => event.artists || []).map(name => [normalize(name), name]));
  fillSelect(document.querySelector("[data-artist-filter]"), artistValues, value => displayByNorm.get(value) || value);
  const states = [...new Set(list.map(event => event.state).filter(Boolean))].sort();
  fillSelect(document.querySelector("[data-state-filter]"), states, state => STATE_NAMES[state] || state);
  setupEventFilters([...grid.querySelectorAll("[data-event-card]")]);
  if (mode === "month") {
    const now = new Date();
    const label = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" }).format(now);
    const title = document.querySelector("[data-current-month-title]");
    if (title) title.textContent = `Christian Hip-Hop Shows in ${label}`;
    document.querySelector("[data-month-show-count]")?.replaceChildren(String(list.length));
    document.querySelector("[data-month-state-count]")?.replaceChildren(String(new Set(list.map(event => event.state).filter(Boolean)).size));
    document.querySelector("[data-month-festival-count]")?.replaceChildren(String(list.filter(event => event.eventType === "festival").length));
  }
}
function friendlyCategory(value) {
  return ({core:"Core CHH",reach:"Reach Records",crossover:"Crossover",group:"Group",legacy:"Legacy"})[value] || "CHH artist";
}
function spotifyInfo(artist) {
  const directProfile = artist.spotifyProfile || (artist.spotifyId ? `https://open.spotify.com/artist/${encodeURIComponent(artist.spotifyId)}` : "");
  if (directProfile) return { url: directProfile, exact: true, status: "Open verified Spotify profile" };
  return { url: "", exact: false, status: "Spotify link pending verification" };
}
function instagramInfo(artist) {
  return artist.instagramProfile ? { url: artist.instagramProfile, status: "Open verified Instagram profile" } : { url: "", status: "Instagram link pending verification" };
}
function youtubeInfo(artist) {
  const official = artist.youtubeProfile || (/youtu\.be|youtube\.com/i.test(artist.officialProfile || "") ? artist.officialProfile : "");
  return official ? { url: official, status: "Open verified YouTube profile" } : { url: "", status: "YouTube link pending verification" };
}
function websiteInfo(artist) {
  const candidate = artist.website || artist.officialWebsite || artist.officialProfile || "";
  const isPlatform = /instagram\.com|open\.spotify\.com|youtu\.be|youtube\.com|music\.apple\.com|bandsintown\.com/i.test(candidate);
  return candidate && !isPlatform ? { url: candidate, status: "Open official website" } : { url: "", status: "Website link pending verification" };
}
function artistImageInfo(artist) {
  if (artist.sourceRegistryVerified !== true) return { url: "", fallbackUrl: "", position: "center" };
  const primaryUrl = localAssetUrl(artist.imageUrl);
  const spotifyFallback = localAssetUrl(spotifyArtistImageUrl(artist));
  return {
    url: primaryUrl || spotifyFallback,
    fallbackUrl: primaryUrl && spotifyFallback && primaryUrl !== spotifyFallback ? spotifyFallback : "",
    position: artist.imagePosition || "center"
  };
}
function handleArtistImageError(image, initial) {
  const fallback = image?.dataset?.fallbackSrc || "";
  if (fallback && image.dataset.fallbackTried !== "true") {
    image.dataset.fallbackTried = "true";
    image.src = fallback;
    return;
  }
  image.onerror = null;
  if (image.parentElement) image.parentElement.textContent = initial;
}
function artistInitial(name) {
  return String(name || "?").trim().charAt(0).toUpperCase() || "?";
}
function platformIcon(label, extraClass = "") {
  const iconClass = ["platform-icon", extraClass].filter(Boolean).join(" ");
  const common = `class="${iconClass}" viewBox="0 0 24 24" aria-hidden="true" focusable="false"`;
  switch (normalize(label)) {
    case "instagram":
      return `<svg ${common}><rect x="3" y="3" width="18" height="18" rx="5" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="17.5" cy="6.5" r="1.25" fill="currentColor"/></svg>`;
    case "spotify":
      return `<svg ${common}><circle cx="12" cy="12" r="10" fill="currentColor"/><path d="M7.2 9.1c3.55-1.02 7.54-.7 10.72.98M8 12.1c2.93-.8 6.25-.54 8.85.73M8.8 15c2.27-.57 4.8-.37 6.83.56" fill="none" stroke="#080808" stroke-width="1.65" stroke-linecap="round"/></svg>`;
    case "youtube":
      return `<svg ${common}><path d="M21.45 7.15a2.95 2.95 0 0 0-2.08-2.09C17.54 4.55 12 4.55 12 4.55s-5.54 0-7.37.51a2.95 2.95 0 0 0-2.08 2.09A30.5 30.5 0 0 0 2.05 12c0 1.62.17 3.24.5 4.85a2.95 2.95 0 0 0 2.08 2.09c1.83.51 7.37.51 7.37.51s5.54 0 7.37-.51a2.95 2.95 0 0 0 2.08-2.09c.33-1.61.5-3.23.5-4.85s-.17-3.24-.5-4.85Z" fill="currentColor"/><path d="m10 15.35 5.2-3.35L10 8.65v6.7Z" fill="#080808"/></svg>`;
    case "website":
      return `<svg ${common}><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M3.5 12h17M12 3c2.35 2.45 3.55 5.45 3.55 9S14.35 18.55 12 21M12 3C9.65 5.45 8.45 8.45 8.45 12S9.65 18.55 12 21" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>`;
    default:
      return `<svg ${common}><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/></svg>`;
  }
}
function compactPlatformLink(label, info, artistName = "") {
  const context = artistName ? ` for ${artistName}` : "";
  const accessibleLabel = info.url ? `Open ${label}${context}` : `${label}${context}: link pending verification`;
  const content = `${platformIcon(label)}<span class="kc-visually-hidden">${esc(accessibleLabel)}</span>`;
  if (!info.url) return `<span class="artist-platform-link is-missing" role="img" aria-label="${esc(accessibleLabel)}" title="${esc(info.status)}">${content}</span>`;
  return `<a class="artist-platform-link" href="${esc(info.url)}" target="_blank" rel="noopener" aria-label="${esc(accessibleLabel)}" title="${esc(info.status)}">${content}</a>`;
}
function optionalCompactPlatformLink(label, info, artistName = "") {
  return info.url ? compactPlatformLink(label, info, artistName) : "";
}
function ensureArtistEnhancementStyles() {
  if (document.getElementById("kc-artist-enhancement-styles")) return;
  const style = document.createElement("style");
  style.id = "kc-artist-enhancement-styles";
  style.textContent = `
    .kc-visually-hidden{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}
    .artist-card-links{gap:10px;align-items:center}
    .artist-platform-link{position:relative;width:42px;height:42px;min-height:42px;padding:0;border-radius:50%;transition:border-color .18s ease,color .18s ease,background .18s ease,transform .18s ease}
    .artist-platform-link .platform-icon{width:22px;height:22px;display:block;flex:0 0 auto}
    .artist-platform-link:hover{transform:translateY(-1px);background:rgba(198,148,60,.08)}
    .artist-platform-link:focus-visible{outline:2px solid var(--gold-light);outline-offset:3px}
    .artist-platform-link.is-missing{opacity:.42;transform:none;background:transparent}
    .profile-platform-card{gap:14px}
    .profile-platform-heading{display:flex;align-items:center;gap:11px}
    .profile-platform-icon{width:31px;height:31px;display:block;flex:0 0 auto;color:var(--cream)}
    .profile-platform-card:hover .profile-platform-icon{color:var(--gold-light)}
    .profile-platform-card.is-missing .profile-platform-icon{color:#777}
    @media(max-width:600px){.artist-platform-link{width:40px;height:40px;min-height:40px}.artist-platform-link .platform-icon{width:21px;height:21px}}
  `;
  document.head.appendChild(style);
}
function renderArtistDirectory() {
  const grid = document.querySelector("[data-artist-grid]");
  if (!grid) return;
  const byArtist = new Map();
  EVENTS.forEach(event => (event.artists || []).forEach(name => {
    const key = normalize(name);
    if (!byArtist.has(key)) byArtist.set(key, []);
    byArtist.get(key).push(event);
  }));
  const enabled = ARTISTS.filter(artist => artist.enabled !== false).sort((a, b) => (a.rosterOrder || 9999) - (b.rosterOrder || 9999) || a.name.localeCompare(b.name));
  grid.innerHTML = enabled.map(artist => {
    const events = byArtist.get(normalize(artist.name)) || [];
    const instagram = instagramInfo(artist);
    const spotify = spotifyInfo(artist);
    const youtube = youtubeInfo(artist);
    const website = websiteInfo(artist);
    const image = artistImageInfo(artist);
    const visual = image.url
      ? `<a class="artist-visual" href="${artistProfileUrl(artist.name)}" aria-label="View ${esc(artist.name)}"><img src="${esc(image.url)}" data-fallback-src="${esc(image.fallbackUrl)}" alt="${esc(artist.name)}" loading="lazy" decoding="async" referrerpolicy="no-referrer" style="object-position:${esc(image.position)}" onerror="handleArtistImageError(this,'${esc(artistInitial(artist.name))}')"></a>`
      : `<a class="artist-visual artist-visual-empty" href="${artistProfileUrl(artist.name)}" aria-label="View ${esc(artist.name)}"></a>`;
    return `<article class="artist-card artist-card-text" data-artist-card data-search="${esc(normalize([artist.name, ...(artist.aliases || []), artist.label].join(" ")))}" data-has-shows="${events.length > 0}">
      ${visual}
      <div class="artist-card-body"><h2><a href="${artistProfileUrl(artist.name)}">${esc(artist.name)}</a></h2><p>${events.length} upcoming show${events.length === 1 ? "" : "s"}</p><div class="artist-card-links">${compactPlatformLink("Instagram", instagram, artist.name)}${compactPlatformLink("Spotify", spotify, artist.name)}${optionalCompactPlatformLink("YouTube", youtube, artist.name)}${optionalCompactPlatformLink("Website", website, artist.name)}</div><div class="artist-card-footer"><a class="text-link" href="${artistProfileUrl(artist.name)}">View artist</a></div></div>
    </article>`;
  }).join("");
  document.querySelector("[data-artist-loading]")?.remove();
  const cards = [...grid.querySelectorAll("[data-artist-card]")];
  const search = document.querySelector("[data-artist-search]");
  const show = document.querySelector("[data-has-shows-filter]");
  const count = document.querySelector("[data-artist-count]");
  const empty = document.querySelector("[data-artist-empty]");
  function apply() {
    const needle = normalize(search?.value);
    const requireShows = Boolean(show?.checked);
    let visible = 0;
    cards.forEach(card => {
      const ok = (!needle || (card.dataset.search || "").includes(needle)) && (!requireShows || card.dataset.hasShows === "true");
      card.hidden = !ok;
      if (ok) visible += 1;
    });
    if (count) count.textContent = `${visible} artist${visible === 1 ? "" : "s"}`;
    if (empty) empty.hidden = visible !== 0;
  }
  search?.addEventListener("input", apply);
  show?.addEventListener("change", apply);
  apply();
}
function platformCard(label, info, artistName = "") {
  const heading = `<span class="profile-platform-heading">${platformIcon(label, "profile-platform-icon")}<span class="profile-platform-label">${esc(label)}</span></span>`;
  if (!info.url) return `<div class="profile-platform-card is-missing" aria-label="${esc(`${label}${artistName ? ` for ${artistName}` : ""}: link pending verification`)}">${heading}<span class="profile-platform-status">${esc(info.status)}</span></div>`;
  return `<a class="profile-platform-card" href="${esc(info.url)}" target="_blank" rel="noopener" aria-label="${esc(`Open ${label}${artistName ? ` for ${artistName}` : ""}`)}">${heading}<span class="profile-platform-status">${esc(info.status)}</span></a>`;
}
function renderArtistProfile() {
  const root = document.querySelector("[data-artist-profile]");
  if (!root) return;
  const name = new URLSearchParams(location.search).get("name") || "";
  const artist = artistConfig(name);
  if (!artist) {
    root.innerHTML = `<section class="page-hero hero-compact"><h1>Artist not found.</h1><a class="primary-button" href="${BASE}artists/">Return to artists</a></section>`;
    return;
  }
  const events = EVENTS.filter(event => (event.artists || []).some(item => normalize(item) === normalize(artist.name))).sort((a, b) => (a.startDate || "").localeCompare(b.startDate || ""));
  const image = artistImageInfo(artist);
  const heroClass = image.url ? "profile-hero" : "profile-hero profile-hero-no-image";
  const visual = image.url
    ? `<div class="profile-visual"><img src="${esc(image.url)}" data-fallback-src="${esc(image.fallbackUrl)}" alt="${esc(artist.name)}" decoding="async" referrerpolicy="no-referrer" style="object-position:${esc(image.position)}" onerror="handleArtistImageError(this,'${esc(artistInitial(artist.name))}')"></div>`
    : "";
  const imageNote = image.url ? "" : '<p class="profile-image-note">Artist image pending direct-file verification.</p>';
  root.innerHTML = `<section class="${heroClass}">${visual}<div><p class="eyebrow">Artist profile</p><h1>${esc(artist.name)}</h1>${imageNote}<div class="profile-platforms">${platformCard("Instagram", instagramInfo(artist), artist.name)}${platformCard("Spotify", spotifyInfo(artist), artist.name)}${platformCard("YouTube", youtubeInfo(artist), artist.name)}${platformCard("Website", websiteInfo(artist), artist.name)}</div><p class="profile-count">${events.length} upcoming U.S.
show${events.length === 1 ? "" : "s"} currently listed.</p></div></section><section class="calendar"><div class="calendar-heading"><div><p class="eyebrow">Verified listings</p><h2>Upcoming ${esc(artist.name)} Shows</h2></div><p class="results-count">${events.length} shows</p></div><div class="event-grid">${events.map(eventCard).join("") || '<div class="empty-panel">No upcoming U.S. shows are currently confirmed.</div>'}</div></section>`;
  document.title = `${artist.name} Shows | The Kingdom Circuit`;
  ensureCanonical(`${location.origin}${BASE}artists/profile/?name=${encodeURIComponent(artist.name)}`);
  setMetaDescription(`Find verified upcoming U.S. shows and official links for ${artist.name}.`);
}
function renderEventDetail() {
  const root = document.querySelector("[data-event-detail]");
  if (!root) return;
  const id = new URLSearchParams(location.search).get("id");
  const event = EVENTS.find(item => item.id === id);
  if (!event) {
    root.innerHTML = `<section class="page-hero hero-compact"><h1>Event not found.</h1><a class="primary-button" href="${BASE}shows/">View all shows</a></section>`;
    return;
  }
  const img = eventImage(event);
  const locationText = [event.city, event.state].filter(Boolean).join(", ");
  root.innerHTML = `<article class="event-detail"><div class="event-detail-media"><img class="${imageClass(event)}" src="${esc(img)}" alt="${esc(event.title)}" style="object-position:${esc(imagePosition(event))}" onerror="this.onerror=null;this.className='event-artwork';this.src='${FALLBACK_EVENT_IMAGE}';"></div><div class="event-detail-copy"><p class="eyebrow">${esc(event.eventType === "festival" ? "Festival" : "Concert")}</p><h1>${esc(event.title)}</h1><p class="artist-line">${artistLinks(event)}</p><dl class="detail-list"><div><dt>Date</dt><dd>${esc(formatDate(event))}</dd></div><div><dt>Venue</dt><dd>${esc(event.venue || "Venue to be announced")}</dd></div><div><dt>Location</dt><dd>${esc(locationText || "Location to be announced")}</dd></div>${event.price ? `<div><dt>Price</dt><dd>${esc(event.price)}</dd></div>` : ""}<div><dt>Source</dt><dd>${esc(sourceText(event))}</dd></div></dl><a class="primary-button" href="${esc(event.officialUrl || event.ticketUrl || "#")}" target="_blank" rel="noopener">Official details</a><p class="disclaimer">Event details, availability, pricing, and lineups may change.
Confirm final information with the official organizer or ticket provider before purchasing or traveling.</p></div></article>`;
  document.title = `${event.title} | The Kingdom Circuit`;
  ensureCanonical(`${location.origin}${BASE}event/?id=${encodeURIComponent(event.id)}`);
  setMetaDescription(`${event.title} in ${locationText || "the United States"}. View verified event details and the official source.`);
}

function ensureCanonical(url) {
  let link = document.querySelector('link[rel="canonical"]');
  if (!link) {
    link = document.createElement("link");
    link.rel = "canonical";
    document.head.appendChild(link);
  }
  link.href = url;
}

function setMetaDescription(text) {
  let meta = document.querySelector('meta[name="description"]');
  if (!meta) {
    meta = document.createElement("meta");
    meta.name = "description";
    document.head.appendChild(meta);
  }
  meta.content = text;
}
async function renderCalendarStatus() {
  const root = document.querySelector("[data-calendar-status]");
  if (!root) return;
  try {
    const response = await fetch(RUN_STATUS_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(String(response.status));
    const status = await response.json();
    const updated = status.lastSuccessfulUpdate || status.lastAttempt;
    const updatedText = updated
      ? new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" }).format(new Date(updated))
      : "Update time unavailable";
    const warnings = Number(status.warningCount || 0);
    const published = Number(status.eventsPublished || EVENTS.length || 0);
    root.innerHTML = `<span><strong>Calendar updated:</strong> ${esc(updatedText)}</span><span>${published} automated listing${published === 1 ? "" : "s"}</span>${warnings ? `<span class="footer-source-warning">${warnings} source check${warnings === 1 ? "" : "s"} unavailable; published listings remain verified.</span>` : ""}`;
    root.hidden = false;
  } catch (error) {
    console.warn("Calendar status was unavailable.", error);
    root.hidden = true;
  }
}
function setMenuOpen(open) {
  const toggle = document.querySelector(".menu-toggle");
  const drawer = document.querySelector(".menu-drawer");
  const backdrop = document.querySelector(".menu-backdrop");
  if (!toggle || !drawer || !backdrop) return;
  toggle.setAttribute("aria-expanded", String(open));
  drawer.setAttribute("aria-hidden", String(!open));
  drawer.classList.toggle("open", open);
  backdrop.hidden = !open;
  document.body.classList.toggle("menu-open", open);
}
document.querySelector(".menu-toggle")?.addEventListener("click", () => setMenuOpen(document.querySelector(".menu-toggle")?.getAttribute("aria-expanded") !== "true"));
document.querySelector(".menu-close")?.addEventListener("click", () => setMenuOpen(false));
document.querySelector(".menu-backdrop")?.addEventListener("click", () => setMenuOpen(false));
document.addEventListener("keydown", event => { if (event.key === "Escape") setMenuOpen(false); });
function setupSubmissionForm() {
  const form = document.querySelector("[data-submission-form]");
  if (!form) return;
  const feedback = form.querySelector("[data-submission-feedback]");
  const submit = form.querySelector("[data-submission-submit]");
  const kind = form.querySelector("[data-submission-kind]");
  const eventName = form.querySelector("[data-event-name]");
  const buttons = [...form.querySelectorAll("[data-submission-mode]")];
  const params = new URLSearchParams(location.search);
  function setMode(value) {
    if (kind) kind.value = value;
    buttons.forEach(button => button.classList.toggle("active", button.dataset.submissionMode === value));
    if (submit) submit.textContent = value === "Correction" ? "Send Correction" : "Send for Review";
  }
  buttons.forEach(button => button.addEventListener("click", () => setMode(button.dataset.submissionMode || "New show")));
  if ((params.get("type") || "").includes("correction")) setMode("Correction");
  if (params.get("event") && eventName) eventName.value = params.get("event");
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    if (feedback) feedback.textContent = "Sending submission...";
    if (submit) submit.disabled = true;
    try {
      const response = await fetch(form.action, { method: "POST", body: new FormData(form), headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error();
      form.reset();
      setMode("New show");
      if (feedback) feedback.textContent = "Submission received. The Kingdom Circuit will review the information before publishing or updating the event.";
    } catch {
      if (feedback) feedback.textContent = "The submission could not be sent. Please try again in a few minutes.";
    } finally {
      if (submit) submit.disabled = false;
    }
  });
}
async function boot() {
  try {
    const [liveEvents, liveArtists, supplemental] = await Promise.all([
      loadJson(LIVE_EVENTS_URL, "events.json"),
      loadJson(LIVE_ARTISTS_URL, "config/artists.json"),
      loadOptionalJson(SUPPLEMENTAL_EVENTS_URL)
    ]);
    ARTISTS = applyArtistOverrides(liveArtists);
    EVENTS = mergeEventLists(liveEvents, supplemental);
  } catch (error) {
    console.error(error);
    document.querySelectorAll(".loading-panel").forEach(element => { element.textContent = "The calendar could not load its data. Please refresh in a moment."; });
    return;
  }
  renderEventList();
  ensureArtistEnhancementStyles();
  renderArtistDirectory();
  renderArtistProfile();
  renderEventDetail();
  setupSubmissionForm();
  renderCalendarStatus();
}
boot();
