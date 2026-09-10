NSE_INDEX_CSV_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
NSE_MAX_SYMBOLS = 300

# The niftyindices constituent CSV load_watchlist() fetches is alphabetical by
# company name, not ranked by size, so slicing it at NSE_MAX_SYMBOLS used to mean
# "first N alphabetically" rather than "top N by market cap." This list is the
# actual ranking: all Nifty 500 constituents ordered by market cap (descending),
# captured 2026-09-10 via yfinance fast_info.marketCap. load_watchlist() sorts the
# fetched constituents against this order before applying NSE_MAX_SYMBOLS, so the
# cut is now a real top-N-by-size cut. A symbol the CSV lists but this ranking
# doesn't know about (new listing since capture) sorts after everything ranked.
# Re-audit the same way DELTA_LISTED_SYMBOLS in the main config is re-audited -
# periodically, and whenever the cut size changes.
NSE_MARKET_CAP_RANK = [
    "RELIANCE.NS", "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "BAJFINANCE.NS", "LT.NS", "HINDUNILVR.NS", "INFY.NS",
    "ADANIENT.NS", "KOTAKBANK.NS", "ADANIPOWER.NS", "ADANIPORTS.NS", "MARUTI.NS", "AXISBANK.NS", "M&M.NS", "HAL.NS",
    "HCLTECH.NS", "ITC.NS", "NTPC.NS", "BAJAJ-AUTO.NS", "JSWSTEEL.NS", "BAJAJFINSV.NS", "ONGC.NS", "ETERNAL.NS",
    "BEL.NS", "NESTLEIND.NS", "COALINDIA.NS", "LICI.NS", "POWERGRID.NS", "HINDZINC.NS", "DIVISLAB.NS", "DMART.NS",
    "ASIANPAINT.NS", "GRASIM.NS", "HINDALCO.NS", "ADANIGREEN.NS", "EICHERMOT.NS", "INDIGO.NS", "IOC.NS", "HYUNDAI.NS",
    "SBILIFE.NS", "ADANIENSOL.NS", "DLF.NS", "PIDILITIND.NS", "CHOLAFIN.NS", "ABB.NS", "JIOFIN.NS", "ICICIAMC.NS",
    "BHEL.NS", "CGPOWER.NS", "BOSCHLTD.NS", "CUMMINSIND.NS", "POWERINDIA.NS", "PNB.NS", "BSE.NS", "LTM.NS",
    "BPCL.NS", "APOLLOHOSP.NS", "POLYCAB.NS", "BANKBARODA.NS", "BAJAJHLDNG.NS", "GROWW.NS", "BRITANNIA.NS", "LENSKART.NS",
    "PFC.NS", "GVT&D.NS", "LODHA.NS", "JINDALSTEL.NS", "INDIANB.NS", "GAIL.NS", "HDFCLIFE.NS", "MUTHOOTFIN.NS",
    "CANBK.NS", "LGEINDIA.NS", "PAYTM.NS", "CIPLA.NS", "ABCAPITAL.NS", "IRFC.NS", "HEROMOTOCO.NS", "LAURUSLABS.NS",
    "HDFCAMC.NS", "MARICO.NS", "INDHOTEL.NS", "GMRAIRPORT.NS", "OFSS.NS", "LLOYDSME.NS", "MAXHEALTH.NS", "MEESHO.NS",
    "INDIAMART.NS", "AMBUJACEM.NS", "INDUSTOWER.NS", "NYKAA.NS", "ASHOKLEY.NS", "JSWENERGY.NS", "MAZDOCK.NS", "AUROPHARMA.NS",
    "DRREDDY.NS", "LUPIN.NS", "BHARATFORG.NS", "MANKIND.NS", "GODREJCP.NS", "IDBI.NS", "PERSISTENT.NS", "FEDERALBNK.NS",
    "MCX.NS", "POLICYBZR.NS", "RECLTD.NS", "DIXON.NS", "NAUKRI.NS", "OIL.NS", "COFORGE.NS", "JSWINFRA.NS",
    "AUBANK.NS", "LTF.NS", "INDUSINDBK.NS", "BHARTIHEXA.NS", "NHPC.NS", "NAM-INDIA.NS", "HINDPETRO.NS", "IDFCFIRSTB.NS",
    "NMDC.NS", "NTPCGREEN.NS", "ICICIGI.NS", "APARINDS.NS", "BAJAJHFL.NS", "HAVELLS.NS", "NATIONALUM.NS", "ICICIPRULI.NS",
    "GLENMARK.NS", "FORTIS.NS", "PHOENIXLTD.NS", "ASTERDM.NS", "DABUR.NS", "PRESTIGE.NS", "ATGL.NS", "ATHERENERG.NS",
    "OBEROIRLTY.NS", "MAHABANK.NS", "BANKINDIA.NS", "BIOCON.NS", "RBLBANK.NS", "KALYANKJIL.NS", "SBICARD.NS", "IOB.NS",
    "JSL.NS", "ALKEM.NS", "MOTILALOFS.NS", "APLAPOLLO.NS", "GICRE.NS", "RADICO.NS", "COROMANDEL.NS", "GODREJPROP.NS",
    "HDBFS.NS", "MRF.NS", "PIRAMALFIN.NS", "BERGEPAINT.NS", "ABBOTINDIA.NS", "LINDEINDIA.NS", "ANTHEM.NS", "FLUOROCHEM.NS",
    "FACT.NS", "HINDCOPPER.NS", "MFSL.NS", "IPCALAB.NS", "M&MFIN.NS", "COLPAL.NS", "GLAND.NS", "GLAXO.NS",
    "AEGISLOG.NS", "CPPLUS.NS", "NAVINFLUOR.NS", "360ONE.NS", "KEI.NS", "AJANTPHARM.NS", "BDL.NS", "MPHASIS.NS",
    "PREMIERENE.NS", "AIIL.NS", "PETRONET.NS", "RVNL.NS", "BALKRISIND.NS", "COCHINSHIP.NS", "PAGEIND.NS", "POONAWALLA.NS",
    "MEDANTA.NS", "ASTRAL.NS", "NH.NS", "KPRMILL.NS", "AIAENG.NS", "CONCOR.NS", "ENDURANCE.NS", "JKCEMENT.NS",
    "GODREJIND.NS", "NLCINDIA.NS", "IRCTC.NS", "EMCURE.NS", "PATANJALI.NS", "3MINDIA.NS", "PWL.NS", "ANANDRATHI.NS",
    "PIIND.NS", "LTTS.NS", "EXIDEIND.NS", "HFCL.NS", "HUDCO.NS", "CRISIL.NS", "PTCIL.NS", "DELHIVERY.NS",
    "HSCL.NS", "DALBHARAT.NS", "ESCORTS.NS", "NUVAMA.NS", "KARURVYSYA.NS", "AEGISVOPAK.NS", "KIRLOSENG.NS", "ITCHOTELS.NS",
    "LALPATHLAB.NS", "IREDA.NS", "MRPL.NS", "ABSLAMC.NS", "JUBLFOOD.NS", "BLUESTARCO.NS", "MANAPPURAM.NS", "CRAFTSMAN.NS",
    "KIMS.NS", "GODFRYPHLP.NS", "PNBHOUSING.NS", "HEXT.NS", "REDINGTON.NS", "NEULANDLAB.NS", "LICHSGFIN.NS", "HONAUT.NS",
    "IKS.NS", "NETWEB.NS", "CHOLAHLDNG.NS", "CDSL.NS", "ACUTAAS.NS", "PPLPHARMA.NS", "ACMESOLAR.NS", "BANDHANBNK.NS",
    "GRSE.NS", "CENTRALBK.NS", "RRKABEL.NS", "ANGELONE.NS", "DATAPATTNS.NS", "APOLLOTYRE.NS", "CGCL.NS", "IIFL.NS",
    "AMBER.NS", "ITI.NS", "ASAHIINDIA.NS", "KPIL.NS", "PFOCUS.NS", "CHENNPETRO.NS", "MSUMI.NS", "GILLETTE.NS",
    "IRB.NS", "AWL.NS", "FORCEMOT.NS", "GABRIEL.NS", "EMMVEE.NS", "ACC.NS", "KAYNES.NS", "GODIGIT.NS",
    "IFCI.NS", "JYOTICNC.NS", "NBCC.NS", "CREDITACC.NS", "DEEPAKNTR.NS", "CUB.NS", "AFFLE.NS", "GRANULES.NS",
    "BELRISE.NS", "ANANTRAJ.NS", "FINCABLES.NS", "CEMPRO.NS", "IGL.NS", "CAPLIPOINT.NS", "BRIGADE.NS", "CARBORUNIV.NS",
    "AADHARHFC.NS", "JINDALSAW.NS", "HBLENGINE.NS", "PINELABS.NS", "GESHIP.NS", "ELGIEQUIP.NS", "CESC.NS", "KAJARIACER.NS",
    "CHALET.NS", "ERIS.NS", "PFIZER.NS", "ATUL.NS", "CASTROLIND.NS", "THELEELA.NS", "GMDCLTD.NS", "AARTIIND.NS",
    "BAYERCROP.NS", "EIHOTEL.NS", "POLYMED.NS", "ONESOURCE.NS", "CAMS.NS", "FSL.NS", "OLAELEC.NS", "CHOICEIN.NS",
    "ABDL.NS", "COHANCE.NS", "BEML.NS", "DEEPAKFERT.NS", "DEVYANI.NS", "CHAMBLFERT.NS", "MINDACORP.NS", "GPIL.NS",
    "PARADEEP.NS", "JSWCEMENT.NS", "JUBLPHARMA.NS", "EMAMILTD.NS", "INDIACEM.NS", "GRAPHITE.NS", "J&KBANK.NS", "NAVA.NS",
    "FIVESTAR.NS", "DCMSHRIRAM.NS", "KFINTECH.NS", "PGEL.NS", "HONASA.NS", "LTFOODS.NS", "ENGINERSIN.NS", "CONCORDBIO.NS",
    "KPITTECH.NS", "ARE&M.NS", "NATCOPHARM.NS", "BALRAMCHIN.NS", "RAINBOW.NS", "CROMPTON.NS", "ABREL.NS", "CARTRADE.NS",
    "NIVABUPA.NS", "CCL.NS", "CIEINDIA.NS", "JSWDULUX.NS", "CANHLIFE.NS", "JBMA.NS", "BIKAJI.NS", "ANURAS.NS",
    "INDGN.NS", "IGIL.NS", "GALLANTT.NS", "ACE.NS", "CEATLTD.NS", "RKFORGE.NS", "PCBL.NS", "DOMS.NS",
    "INOXWIND.NS", "EIDPARRY.NS", "NSLNISP.NS", "HOMEFIRST.NS", "APTUS.NS", "GRAVITA.NS", "JMFINANCIL.NS", "PVRINOX.NS",
    "NUVOCO.NS", "BLUEDART.NS", "CYIENT.NS", "JPPOWER.NS", "KEC.NS", "SBFC.NS", "MGL.NS", "IRCON.NS",
    "JUBLINGREA.NS", "CANFINHOME.NS", "IEX.NS", "JWL.NS", "JKTYRE.NS", "ABLBL.NS", "AAVAS.NS", "RITES.NS",
    "JAINREC.NS", "BBTC.NS", "BLUEJET.NS", "OLECTRA.NS", "BLS.NS", "INTELLECT.NS", "AFCONS.NS", "ELECON.NS",
    "MMTC.NS", "RPOWER.NS", "CLEAN.NS", "NCC.NS", "RAILTEL.NS", "BATAINDIA.NS", "LEMONTREE.NS", "FIRSTCRY.NS",
    "RHIM.NS", "BSOFT.NS", "NEWGEN.NS", "ABFRL.NS", "LATENTVIEW.NS", "MAPMYINDIA.NS", "HEG.NS",
]

FALLBACK_WATCHLIST = [
    "RELIANCE.NS", "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "BAJFINANCE.NS", "LT.NS", "HINDUNILVR.NS", "INFY.NS",
    "ADANIENT.NS", "KOTAKBANK.NS", "ADANIPOWER.NS", "ADANIPORTS.NS", "MARUTI.NS", "AXISBANK.NS", "M&M.NS", "HAL.NS",
    "HCLTECH.NS", "ITC.NS", "NTPC.NS", "BAJAJ-AUTO.NS", "JSWSTEEL.NS", "BAJAJFINSV.NS", "ONGC.NS", "ETERNAL.NS",
    "BEL.NS", "NESTLEIND.NS", "COALINDIA.NS", "LICI.NS", "POWERGRID.NS", "HINDZINC.NS", "DIVISLAB.NS", "DMART.NS",
    "ASIANPAINT.NS", "GRASIM.NS", "HINDALCO.NS", "ADANIGREEN.NS", "EICHERMOT.NS", "INDIGO.NS", "IOC.NS", "HYUNDAI.NS",
    "SBILIFE.NS", "ADANIENSOL.NS", "DLF.NS", "PIDILITIND.NS", "CHOLAFIN.NS", "ABB.NS", "JIOFIN.NS", "ICICIAMC.NS",
    "BHEL.NS", "CGPOWER.NS", "BOSCHLTD.NS", "CUMMINSIND.NS", "POWERINDIA.NS", "PNB.NS", "BSE.NS", "LTM.NS",
    "BPCL.NS", "APOLLOHOSP.NS", "POLYCAB.NS", "BANKBARODA.NS", "BAJAJHLDNG.NS", "GROWW.NS", "BRITANNIA.NS", "LENSKART.NS",
    "PFC.NS", "GVT&D.NS", "LODHA.NS", "JINDALSTEL.NS", "INDIANB.NS", "GAIL.NS", "HDFCLIFE.NS", "MUTHOOTFIN.NS",
    "CANBK.NS", "LGEINDIA.NS", "PAYTM.NS", "CIPLA.NS", "ABCAPITAL.NS", "IRFC.NS", "HEROMOTOCO.NS", "LAURUSLABS.NS",
    "HDFCAMC.NS", "MARICO.NS", "INDHOTEL.NS", "GMRAIRPORT.NS", "OFSS.NS", "LLOYDSME.NS", "MAXHEALTH.NS", "MEESHO.NS",
    "INDIAMART.NS", "AMBUJACEM.NS", "INDUSTOWER.NS", "NYKAA.NS", "ASHOKLEY.NS", "JSWENERGY.NS", "MAZDOCK.NS", "AUROPHARMA.NS",
    "DRREDDY.NS", "LUPIN.NS", "BHARATFORG.NS", "MANKIND.NS",
]

TIMEFRAME = "4h"
SOURCE_INTERVAL = "1h"
SOURCE_PERIOD = "700d"
MARKET_TIMEZONE = "Asia/Kolkata"
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"
ALERT_SCAN_START = "09:00"
TRADE_START = "09:15"
STRATEGY_CUTOFF = "15:10"
REPORT_TIME = "16:30"

OHLCV_LIMIT = 500
SWING_LENGTH = 10
ATR_PERIOD = 50
BOX_WIDTH = 2.5
# NSE keeps its 500-bar lookback: the exchange trades 6.25 hours a day,
# so 500 30m candles is already forty sessions, not ten days. Only the
# cap moves, so a level from two months ago is not dropped in favour of a
# newer one.
HISTORY_OF_ZONES_TO_KEEP = 60
# Matches the Pine indicator's f_check_overlapping, which rejects a new zone
# whose midpoint sits within atr * 2 of an existing one.
OVERLAP_ATR = 2.0
# The Pine indicator applies no wick, body-ratio or departure test - every
# confirmed pivot becomes a zone. These are kept only as metadata on the zone
# for the rating and for later analysis, never as filters, so the zone set
# matches what the chart draws.
MIN_WICK_ATR = 0.15
MIN_WICK_TO_BODY = 1.5
MIN_DEPARTURE_ATR = 0.75
# Zones are a fixed atr * (BOX_WIDTH / 10) band anchored on the pivot extreme,
# exactly as the indicator draws them, so no separate padding applies.
ZONE_PADDING_ATR = 0.0

# Distance is measured to the entry edge - the one price reaches first -
# so this is "how far is price from the level I would actually trade".
# Alert as soon as a symbol comes within MAX_DISTANCE_PCT of it.
MIN_DISTANCE_PCT = 0.0
MAX_DISTANCE_PCT = 0.20
REARM_FACTOR = 1.25
# 0 disables the over-touch veto. The Pine indicator counts no touches and
# never retires a zone for being revisited - only a close through it kills the
# zone - so any positive value here drops levels the chart still shows.
# Back-to-back candles sitting on a zone mean price is grinding through it
# rather than reacting to it - thin volume, no rejection. Two consecutive
# touching candles retire the zone. This is deliberately stricter than the
# Pine indicator, which has no touch veto at all: the indicator draws every
# level, this decides which are worth an alert.
MAX_CONSECUTIVE_ZONE_TOUCHES = 2

# A zone has to stand before it means anything. A level confirmed a candle
# or two ago that price is already sitting on was never defended - it is
# just the recent high or low, and alerting on it produces the small, risky
# levels that are not worth a trade. Age is counted from confirmation, so a
# 30m zone must survive twenty candles - about ten hours - before it can
# raise an alert, and a 4h zone a little over three days.
# Twenty rather than fifteen because both markets said so: replayed on 5m
# candles, the alerts this blocks earned 0.054R on NSE and 0.389R on
# crypto, against 0.122R and 0.564R for the ones that survive it.
MIN_ZONE_AGE_CANDLES = 20
# Shortest gap between two scans of the same timeframe. Every workflow is
# also dispatched by an external scheduler, so cron in this repo means each
# scan would otherwise run twice, minutes apart.
MIN_SCAN_INTERVAL_SECONDS = 8 * 60
SCAN_SLEEP = 300
SCAN_WORKERS = 8
ALERT_COOLDOWN_SECONDS = 4 * 60 * 60
ALERT_RANGE_FILTER_SIGNALS = True
SIGNAL_ALERT_COOLDOWN_SECONDS = 4 * 60 * 60

PRINT_SCAN_SUMMARY = True
PRINT_ALERTS_TO_CONSOLE = True

# Display-only ratings for the isolated NSE 30m backtest phase.
SHOW_ZONE_RATINGS = False
ZONE_RATING_BASE = 4
# Show the transparent rule-based quality score on every 4h NSE zone.
SHOW_4H_ZONE_SCORES = True

DISCORD_WEBHOOK_URL = ""
DISCORD_NSE_WEBHOOK_URL = ""
DISCORD_STATUS_WEBHOOK_URL = ""
