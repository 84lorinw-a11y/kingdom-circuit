"use strict";

console.info("Kingdom Circuit production multipage build loaded");
const BASE = "/";
const LIVE_EVENTS_URL = `${BASE}events.json`;
const LIVE_ARTISTS_URL = `${BASE}config/artists.json`;
const SITE_BUILD = "production-v3-mobile-artist-circuit";
const SUPPLEMENTAL_EVENTS_URL = `${BASE}supplemental-events.json?v=2`;
const RUN_STATUS_URL = `${BASE}run-status.json`;
const FALLBACK_EVENT_IMAGE = `${BASE}assets/event-fallback.webp`;
const ARTIST_SUBMISSION_ENDPOINT = "https://formspree.io/f/mljreawj";
const VERIFIED_ARTIST_IMAGE_ENDPOINT = "https://open.voidware.de/artist/";
let PLATFORM_ICON_SEQUENCE = 0;
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
    case "instagram": { 
      const gradientId = `kc-instagram-${++PLATFORM_ICON_SEQUENCE}`;
      return `<svg ${common}><defs><radialGradient id="${gradientId}-glow" cx="30%" cy="100%" r="105%"><stop offset="0" stop-color="#feda75"/><stop offset=".3" stop-color="#fa7e1e"/><stop offset=".61" stop-color="#e1306c"/><stop offset=".82" stop-color="#c13584"/><stop offset="1" stop-color="#833ab4"/></radialGradient><linearGradient id="${gradientId}-sky" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#405de6"/><stop offset=".42" stop-color="#5851db" stop-opacity=".8"/><stop offset="1" stop-color="#833ab4" stop-opacity="0"/></linearGradient></defs><rect x="1" y="1" width="22" height="22" rx="6.4" fill="url(#${gradientId}-glow)"/><rect x="1" y="1" width="22" height="22" rx="6.4" fill="url(#${gradientId}-sky)"/><rect x="6.1" y="6.1" width="11.8" height="11.8" rx="3.7" fill="none" stroke="#fff" stroke-width="1.85"/><circle cx="12" cy="12" r="3" fill="none" stroke="#fff" stroke-width="1.85"/><circle cx="17.25" cy="6.85" r="1.15" fill="#fff"/></svg>`;
    }
    case "spotify":
      return `<svg ${common}><circle cx="12" cy="12" r="11" fill="#1ed760"/><path d="M6.35 9.05c3.92-1.12 8.32-.77 11.83 1.08M7.2 12.15c3.22-.88 6.87-.59 9.74.81M8.05 15.1c2.5-.63 5.29-.41 7.52.62" fill="none" stroke="#090909" stroke-width="1.75" stroke-linecap="round"/></svg>`;
    case "youtube":
      return `<svg ${common}><rect x="1" y="4.25" width="22" height="15.5" rx="4.4" fill="#ff0033"/><path d="m10 8.45 6 3.55-6 3.55v-7.1Z" fill="#fff"/></svg>`;
    case "website":
      return `<svg ${common}><circle cx="12" cy="12" r="9.5" fill="none" stroke="#e3b75d" stroke-width="1.9"/><path d="M2.75 12h18.5M12 2.5c2.45 2.55 3.72 5.7 3.72 9.5S14.45 18.95 12 21.5M12 2.5C9.55 5.05 8.28 8.2 8.28 12S9.55 18.95 12 21.5" fill="none" stroke="#e3b75d" stroke-width="1.65" stroke-linecap="round"/></svg>`;
    default:
      return `<svg ${common}><path d="M5 12h14M12 5v14" fill="none" stroke="#e3b75d" stroke-width="2" stroke-linecap="round"/></svg>`;
  }
}
function compactPlatformLink(label, info, artistName = "") {
  const context = artistName ? ` for ${artistName}` : "";
  const platform = normalize(label).replace(/\s+/g, "-");
  const accessibleLabel = info.url ? `Open ${label}${context}` : `${label}${context}: link pending verification`;
  const content = `${platformIcon(label)}<span class="kc-visually-hidden">${esc(accessibleLabel)}</span>`;
  if (!info.url) return `<span class="artist-platform-link artist-platform-link--${esc(platform)} is-missing" role="img" aria-label="${esc(accessibleLabel)}" title="${esc(info.status)}">${content}</span>`;
  return `<a class="artist-platform-link artist-platform-link--${esc(platform)}" href="${esc(info.url)}" target="_blank" rel="noopener" aria-label="${esc(accessibleLabel)}" title="${esc(info.status)}" data-artist-social="${esc(label)}" data-artist-name="${esc(artistName)}">${content}</a>`;
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
    [data-artist-grid]{align-items:stretch}
    .artist-card{min-width:0;min-height:0!important;display:flex;flex-direction:column;scroll-margin-top:112px}
    .artist-visual,.artist-visual-empty{position:relative;display:block;width:100%;aspect-ratio:1/1!important;min-height:0!important;overflow:hidden;background:linear-gradient(145deg,#17120a,#080808);border-bottom:1px solid var(--line,var(--border,#2d2d2d))}
    .artist-visual img{position:absolute;inset:0;display:block;width:100%!important;height:100%!important;object-fit:cover!important;object-position:center;background:#090909;transition:transform .28s ease}
    .artist-card:hover .artist-visual img{transform:scale(1.025)}
    .artist-visual-empty{display:grid;place-items:center}
    .artist-card-body{display:flex;flex:1;flex-direction:column;min-width:0}
    .artist-card-links{display:flex;gap:11px;align-items:center;flex-wrap:wrap;margin-top:13px}
    .artist-platform-link{position:relative;display:inline-flex!important;align-items:center;justify-content:center;width:32px!important;height:32px!important;min-width:32px!important;min-height:32px!important;padding:0!important;border:0!important;border-radius:0!important;background:transparent!important;color:inherit!important;text-decoration:none;box-shadow:none!important;transition:transform .18s ease,filter .18s ease,opacity .18s ease}
    .artist-platform-link .platform-icon{display:block;width:28px;height:28px;flex:0 0 auto;filter:drop-shadow(0 2px 7px rgba(0,0,0,.3))}
    .artist-platform-link:hover{transform:translateY(-2px) scale(1.08);filter:brightness(1.08)}
    .artist-platform-link:focus-visible{outline:2px solid var(--gold-light,#e0bd72);outline-offset:4px;border-radius:4px!important}
    .artist-platform-link.is-missing{opacity:.2;transform:none!important;filter:grayscale(1)}
    .artist-card-footer .text-link{display:inline-flex;align-items:center;gap:7px;text-transform:uppercase;letter-spacing:.085em;font-size:.76rem;text-decoration:none}
    .artist-card-footer .text-link::after{content:"→";font-size:1rem;transition:transform .18s ease}
    .artist-card-footer .text-link:hover::after{transform:translateX(3px)}
    .profile-platform-card{gap:14px}
    .profile-platform-heading{display:flex;align-items:center;gap:11px}
    .profile-platform-icon{display:block;width:31px;height:31px;flex:0 0 auto}
    .profile-platform-card.is-missing .profile-platform-icon{opacity:.3;filter:grayscale(1)}
    .kc-directory-dashboard{display:grid;grid-template-columns:minmax(170px,.75fr) minmax(240px,1.25fr) minmax(260px,1.35fr);gap:16px;margin:8px 0 26px;padding:18px;border:1px solid rgba(198,148,60,.34);border-radius:18px;background:linear-gradient(135deg,rgba(198,148,60,.11),rgba(15,15,15,.98) 42%,#0b0b0b);box-shadow:0 18px 45px rgba(0,0,0,.2)}
    .kc-directory-total,.kc-artist-jump,.kc-artist-submit-prompt{min-width:0;border:1px solid rgba(255,255,255,.07);border-radius:14px;background:rgba(8,8,8,.58);padding:16px}
    .kc-directory-total{display:flex;flex-direction:column;justify-content:center}
    .kc-directory-number{display:block;color:var(--gold-light,#e0bd72);font-size:clamp(3.7rem,7vw,6.3rem);font-weight:950;line-height:.78;letter-spacing:-.065em}
    .kc-directory-label{display:block;margin-top:14px;color:var(--cream,var(--text,#f2efe7));font-size:.72rem;font-weight:900;letter-spacing:.15em;text-transform:uppercase}
    .kc-directory-note{display:block;margin-top:7px;color:var(--muted,#a7a39b);font-size:.82rem}
    .kc-control-label{display:block;margin:0 0 9px;color:var(--gold-light,#e0bd72);font-size:.7rem;font-weight:900;letter-spacing:.13em;text-transform:uppercase}
    .kc-artist-jump select{width:100%;min-height:48px;border:1px solid #484848;border-radius:10px;background:#080808;color:var(--cream,var(--text,#f2efe7));padding:0 42px 0 13px;font:inherit;font-weight:800;cursor:pointer}
    .kc-artist-jump p,.kc-artist-submit-prompt p{margin:10px 0 0;color:var(--muted,#a7a39b);font-size:.83rem;line-height:1.45}
    .kc-artist-submit-prompt{display:flex;flex-direction:column;justify-content:center;align-items:flex-start}
    .kc-artist-submit-prompt strong{font-size:1.35rem;line-height:1.03;text-transform:uppercase;letter-spacing:-.025em}
    .kc-put-us-on{margin-top:14px;border:1px solid var(--gold,#c69a46);border-radius:999px;background:var(--gold,#c69a46);color:#080808;padding:11px 18px;font:inherit;font-size:.78rem;font-weight:950;letter-spacing:.105em;text-transform:uppercase;cursor:pointer;transition:transform .18s ease,filter .18s ease}
    .kc-put-us-on:hover{transform:translateY(-2px);filter:brightness(1.08)}
    .kc-put-us-on:focus-visible{outline:2px solid var(--cream,var(--text,#f2efe7));outline-offset:3px}
    .artist-card.is-jump-target{border-color:var(--gold,#c69a46)!important;box-shadow:0 0 0 2px rgba(198,148,60,.28),0 16px 36px rgba(0,0,0,.38);animation:kcArtistPulse .9s ease}
    @keyframes kcArtistPulse{0%{transform:scale(.98)}45%{transform:scale(1.015)}100%{transform:scale(1)}}
    .kc-artist-dialog{width:min(620px,calc(100vw - 28px));max-height:calc(100vh - 32px);overflow:auto;border:1px solid rgba(198,148,60,.55);border-radius:20px;background:#0d0d0d;color:var(--cream,var(--text,#f2efe7));padding:0;box-shadow:0 30px 90px rgba(0,0,0,.72)}
    .kc-artist-dialog::backdrop{background:rgba(0,0,0,.78);backdrop-filter:blur(4px)}
    .kc-artist-dialog-inner{padding:24px}
    .kc-artist-dialog-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;padding-bottom:18px;border-bottom:1px solid var(--line,var(--border,#2d2d2d))}
    .kc-artist-dialog-head h2{margin:4px 0 0;font-size:clamp(2rem,7vw,3.4rem);line-height:.9;text-transform:uppercase;letter-spacing:-.045em}
    .kc-artist-dialog-close{display:grid;place-items:center;width:42px;height:42px;flex:0 0 auto;border:1px solid #555;border-radius:50%;background:transparent;color:var(--cream,var(--text,#f2efe7));font-size:1.55rem;cursor:pointer}
    .kc-artist-dialog-copy{margin:15px 0 19px;color:var(--muted)}
    .kc-artist-form{display:grid;grid-template-columns:1fr 1fr;gap:13px}
    .kc-artist-form .kc-field{display:grid;gap:7px}
    .kc-artist-form .kc-field-wide{grid-column:1/-1}
    .kc-artist-form label{color:var(--muted,#a7a39b);font-size:.7rem;font-weight:900;letter-spacing:.11em;text-transform:uppercase}
    .kc-artist-form input,.kc-artist-form textarea{width:100%;border:1px solid #464646;border-radius:10px;background:#080808;color:var(--cream,var(--text,#f2efe7));padding:13px;font:inherit}
    .kc-artist-form textarea{min-height:96px;resize:vertical}
    .kc-artist-form input:focus,.kc-artist-form textarea:focus{outline:2px solid rgba(227,183,93,.72);outline-offset:1px;border-color:var(--gold,#c69a46)}
    .kc-artist-form-actions{grid-column:1/-1;display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:4px}
    .kc-artist-form-submit{border:1px solid var(--gold,#c69a46);border-radius:999px;background:var(--gold,#c69a46);color:#080808;padding:12px 18px;font:inherit;font-weight:950;text-transform:uppercase;letter-spacing:.09em;cursor:pointer}
    .kc-artist-form-submit:disabled{opacity:.55;cursor:wait}
    .kc-artist-form-feedback{min-height:1.4em;margin:0;color:var(--muted,#a7a39b);font-size:.86rem}
    .kc-artist-form-feedback.is-success{color:#8bd8a5}
    .kc-artist-form-feedback.is-error{color:#ff9c9c}
    @media(max-width:900px){.kc-directory-dashboard{grid-template-columns:1fr 1fr}.kc-artist-submit-prompt{grid-column:1/-1}}
    @media(max-width:640px){
      [data-artist-grid]{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:10px!important}
      .artist-card{border-radius:13px!important}
      .artist-visual,.artist-visual-empty{aspect-ratio:1/1!important}
      .artist-card-body{padding:11px!important;min-height:134px}
      .artist-card h2,.artist-card-body>h2{margin:0!important;font-size:clamp(.96rem,4.5vw,1.14rem)!important;line-height:1.04;letter-spacing:-.025em;overflow-wrap:anywhere}
      .artist-card-body>p:not(.artist-category){margin:7px 0 0!important;font-size:.74rem!important;line-height:1.25}
      .artist-card-links{gap:7px;margin-top:10px}
      .artist-platform-link{width:29px!important;height:29px!important;min-width:29px!important;min-height:29px!important}
      .artist-platform-link .platform-icon{width:25px;height:25px}
      .artist-card-footer{padding-top:11px!important}
      .artist-card-footer .text-link{font-size:.68rem;letter-spacing:.075em}
      [data-artist-directory] .directory-toolbar{gap:12px!important;margin-bottom:14px!important}
      [data-artist-directory] .check-field{padding-bottom:0!important;min-height:38px}
      [data-artist-directory] .results-count{margin:0!important;font-size:.86rem}
      .kc-directory-dashboard{grid-template-columns:minmax(112px,.76fr) minmax(0,1.24fr);gap:9px;margin:3px 0 18px;padding:10px;border-radius:15px}
      .kc-directory-total,.kc-artist-jump,.kc-artist-submit-prompt{padding:12px;border-radius:12px}
      .kc-directory-total{grid-column:1;grid-row:1;padding:10px}
      .kc-directory-number{font-size:4.2rem}
      .kc-directory-label{margin-top:10px;font-size:.64rem;line-height:1.35}
      .kc-directory-note{font-size:.72rem;line-height:1.4}
      .kc-artist-submit-prompt{grid-column:2;grid-row:1;padding:12px}
      .kc-artist-submit-prompt strong{font-size:1.02rem;line-height:1.02}
      .kc-artist-submit-prompt p{margin-top:7px;font-size:.72rem;line-height:1.35}
      .kc-put-us-on{width:100%;margin-top:10px;padding:10px 11px;font-size:.7rem}
      .kc-artist-jump{grid-column:1/-1;grid-row:2}
      .kc-artist-jump p{margin-top:7px;font-size:.76rem}
      .kc-artist-dialog-inner{padding:19px}
      .kc-artist-form{grid-template-columns:1fr}
      .kc-artist-form .kc-field-wide,.kc-artist-form-actions{grid-column:auto}
      .profile-platform-icon{width:29px;height:29px}
    }
    @media(max-width:380px){[data-artist-grid]{gap:8px!important}.artist-card-body{padding:9px!important;min-height:128px}.artist-platform-link{width:26px!important;height:26px!important;min-width:26px!important;min-height:26px!important}.artist-platform-link .platform-icon{width:23px;height:23px}.artist-card-links{gap:4px}.kc-directory-dashboard{grid-template-columns:minmax(104px,.74fr) minmax(0,1.26fr)}.kc-directory-number{font-size:3.75rem}.kc-directory-total{padding:8px}.kc-directory-note{display:none}.kc-artist-jump,.kc-artist-submit-prompt{padding:10px}}
  `;
  document.head.appendChild(style);
}
function trackArtistInteraction(action, artistName = "", platform = "") {
  if (typeof window.gtag !== "function") return;
  window.gtag("event", action, {
    artist_name: artistName,
    platform,
    page_location: window.location.href
  });
}
function ensureArtistSuggestionDialog() {
  let dialog = document.querySelector("[data-kc-artist-dialog]");
  if (dialog) return dialog;
  dialog = document.createElement("dialog");
  dialog.className = "kc-artist-dialog";
  dialog.setAttribute("data-kc-artist-dialog", "");
  dialog.innerHTML = `<div class="kc-artist-dialog-inner"><div class="kc-artist-dialog-head"><div><p class="eyebrow">Build the circuit</p><h2>Put Us On</h2></div><button class="kc-artist-dialog-close" type="button" aria-label="Close artist submission">×</button></div><p class="kc-artist-dialog-copy">Know a Christian hip-hop artist or group we should be tracking? Send one official link. Every submission is reviewed before it is added.</p><form class="kc-artist-form" data-kc-artist-form action="${esc(ARTIST_SUBMISSION_ENDPOINT)}" method="post"><input type="hidden" name="submission_type" value="Artist suggestion - missing from roster"><input type="hidden" name="_subject" value="Kingdom Circuit missing artist suggestion"><label class="kc-field kc-field-wide">Artist or group name<input name="artist_name" autocomplete="off" required></label><label class="kc-field kc-field-wide">Official artist link<input name="official_url" type="url" inputmode="url" placeholder="https://" required></label><label class="kc-field">Your name (optional)<input name="submitted_by" autocomplete="name"></label><label class="kc-field">Your email (optional)<input name="reply_to" type="email" autocomplete="email"></label><label class="kc-field kc-field-wide">Why should they be in the circuit? (optional)<textarea name="notes" placeholder="CHH releases, city, label, official socials, or upcoming shows"></textarea></label><div class="kc-artist-form-actions"><button class="kc-artist-form-submit" type="submit">Send Artist</button><p class="kc-artist-form-feedback" role="status" aria-live="polite"></p></div></form></div>`;
  document.body.appendChild(dialog);
  const close = dialog.querySelector(".kc-artist-dialog-close");
  const form = dialog.querySelector("[data-kc-artist-form]");
  const submit = dialog.querySelector(".kc-artist-form-submit");
  const feedback = dialog.querySelector(".kc-artist-form-feedback");
  close?.addEventListener("click", () => {
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
  });
  dialog.addEventListener("click", event => {
    if (event.target !== dialog) return;
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
  });
  form?.addEventListener("submit", async event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    feedback.className = "kc-artist-form-feedback";
    feedback.textContent = "Sending artist suggestion...";
    submit.disabled = true;
    const formData = new FormData(form);
    formData.set("page_url", window.location.href);
    formData.set("submitted_at", new Date().toISOString());
    try {
      const response = await fetch(form.action, { method: "POST", body: formData, headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`Artist suggestion failed: ${response.status}`);
      const artistName = String(formData.get("artist_name") || "");
      form.reset();
      feedback.className = "kc-artist-form-feedback is-success";
      feedback.textContent = "Artist submitted. We will verify the official sources before adding them.";
      trackArtistInteraction("artist_suggestion_submit", artistName);
    } catch (error) {
      console.error(error);
      feedback.className = "kc-artist-form-feedback is-error";
      feedback.textContent = "The suggestion could not be sent. Please try again in a few minutes.";
    } finally {
      submit.disabled = false;
    }
  });
  return dialog;
}
function openArtistSuggestionDialog() {
  const dialog = ensureArtistSuggestionDialog();
  trackArtistInteraction("artist_suggestion_open");
  if (typeof dialog.showModal === "function") dialog.showModal();
  else dialog.setAttribute("open", "");
  window.setTimeout(() => dialog.querySelector('input[name="artist_name"]')?.focus(), 50);
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
  grid.innerHTML = enabled.map((artist, index) => {
    const events = byArtist.get(normalize(artist.name)) || [];
    const instagram = instagramInfo(artist);
    const spotify = spotifyInfo(artist);
    const youtube = youtubeInfo(artist);
    const website = websiteInfo(artist);
    const image = artistImageInfo(artist);
    const loading = index < 8 ? "eager" : "lazy";
    const priority = index < 4 ? ' fetchpriority="high"' : "";
    const visual = image.url
      ? `<a class="artist-visual" href="${artistProfileUrl(artist.name)}" aria-label="Open ${esc(artist.name)} profile"><img src="${esc(image.url)}" data-fallback-src="${esc(image.fallbackUrl)}" alt="${esc(artist.name)}" loading="${loading}" decoding="async"${priority} referrerpolicy="no-referrer" style="object-position:${esc(image.position)}" onerror="handleArtistImageError(this,'${esc(artistInitial(artist.name))}')"></a>`
      : `<a class="artist-visual artist-visual-empty" href="${artistProfileUrl(artist.name)}" aria-label="Open ${esc(artist.name)} profile"></a>`;
    return `<article class="artist-card artist-card-text" data-artist-card data-artist-key="${esc(normalize(artist.name))}" data-search="${esc(normalize([artist.name, ...(artist.aliases || []), artist.label].join(" ")))}" data-has-shows="${events.length > 0}">
      ${visual}
      <div class="artist-card-body"><h2><a href="${artistProfileUrl(artist.name)}">${esc(artist.name)}</a></h2><p>${events.length} upcoming show${events.length === 1 ? "" : "s"}</p><div class="artist-card-links">${compactPlatformLink("Instagram", instagram, artist.name)}${compactPlatformLink("Spotify", spotify, artist.name)}${optionalCompactPlatformLink("YouTube", youtube, artist.name)}${optionalCompactPlatformLink("Website", website, artist.name)}</div><div class="artist-card-footer"><a class="text-link" href="${artistProfileUrl(artist.name)}">Tap In</a></div></div>
    </article>`;
  }).join("");
  document.querySelector("[data-artist-loading]")?.remove();
  document.querySelector("[data-kc-directory-dashboard]")?.remove();
  const cards = [...grid.querySelectorAll("[data-artist-card]")];
  const search = document.querySelector("[data-artist-search]");
  const show = document.querySelector("[data-has-shows-filter]");
  const count = document.querySelector("[data-artist-count]");
  const empty = document.querySelector("[data-artist-empty]");
  const dashboard = document.createElement("section");
  dashboard.className = "kc-directory-dashboard";
  dashboard.setAttribute("data-kc-directory-dashboard", "");
  dashboard.setAttribute("aria-label", "Artist directory tools");
  dashboard.innerHTML = `<div class="kc-directory-total"><span class="kc-directory-number">${enabled.length}</span><span class="kc-directory-label">Artists in the circuit</span><span class="kc-directory-note">Official links. Upcoming shows. One CHH directory.</span></div><div class="kc-artist-jump"><label class="kc-control-label" for="kc-artist-jump-select">Scroll &amp; select an artist</label><select id="kc-artist-jump-select" data-kc-artist-jump><option value="">Choose an artist</option>${enabled.map(artist => `<option value="${esc(normalize(artist.name))}">${esc(artist.name)}</option>`).join("")}</select><p>Pick a name and jump straight to their card.</p></div><div class="kc-artist-submit-prompt"><strong>Who are we missing?</strong><p>Know a Christian hip-hop artist we missed? Put us on. Every source is reviewed before it goes live.</p><button class="kc-put-us-on" type="button" data-kc-open-artist-submit>Put Us On</button></div>`;
  grid.before(dashboard);
  const jump = dashboard.querySelector("[data-kc-artist-jump]");
  dashboard.querySelector("[data-kc-open-artist-submit]")?.addEventListener("click", openArtistSuggestionDialog);
  function apply() {
    const needle = normalize(search?.value);
    const requireShows = Boolean(show?.checked);
    let visible = 0;
    cards.forEach(card => {
      const ok = (!needle || (card.dataset.search || "").includes(needle)) && (!requireShows || card.dataset.hasShows === "true");
      card.hidden = !ok;
      if (ok) visible += 1;
    });
    if (count) count.textContent = visible === enabled.length ? `${visible} artists` : `${visible} showing · ${enabled.length} total`;
    if (empty) empty.hidden = visible !== 0;
  }
  search?.addEventListener("input", () => {
    if (jump) jump.value = "";
    apply();
  });
  show?.addEventListener("change", apply);
  jump?.addEventListener("change", () => {
    const key = jump.value;
    if (!key) return;
    if (search) search.value = "";
    if (show) show.checked = false;
    apply();
    const target = cards.find(card => card.dataset.artistKey === key);
    if (!target) return;
    cards.forEach(card => card.classList.remove("is-jump-target"));
    target.classList.add("is-jump-target");
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    window.setTimeout(() => target.classList.remove("is-jump-target"), 1800);
    const artist = enabled.find(item => normalize(item.name) === key);
    trackArtistInteraction("artist_jump_select", artist?.name || key);
  });
  grid.addEventListener("click", event => {
    const social = event.target.closest?.("[data-artist-social]");
    if (social) trackArtistInteraction("artist_social_click", social.dataset.artistName || "", social.dataset.artistSocial || "");
  });
  apply();
}
function platformCard(label, info, artistName = "") {
  const heading = `<span class="profile-platform-heading">${platformIcon(label, "profile-platform-icon")}<span class="profile-platform-label">${esc(label)}</span></span>`;
  if (!info.url) return `<div class="profile-platform-card is-missing" aria-label="${esc(`${label}${artistName ? ` for ${artistName}` : ""}: link pending verification`)}">${heading}<span class="profile-platform-status">${esc(info.status)}</span></div>`;
  return `<a class="profile-platform-card" href="${esc(info.url)}" target="_blank" rel="noopener" aria-label="${esc(`Open ${label}${artistName ? ` for ${artistName}` : ""}`)}" data-artist-social="${esc(label)}" data-artist-name="${esc(artistName)}">${heading}<span class="profile-platform-status">${esc(info.status)}</span></a>`;
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
  root.querySelectorAll("[data-artist-social]").forEach(link => link.addEventListener("click", () => trackArtistInteraction("artist_social_click", link.dataset.artistName || artist.name, link.dataset.artistSocial || "")));
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
