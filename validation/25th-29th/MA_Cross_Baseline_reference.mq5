#property copyright "OpenAI Codex"
#property version   "1.00"
#property strict

input string            InpTradeTag                = "MA_CROSS_BASELINE";
input long              InpMagicNumber             = 26051501;
input string            InpSymbol                  = "";
input ENUM_TIMEFRAMES   InpSignalTimeframe         = PERIOD_M1;
input ENUM_MA_METHOD    InpFastMaMethod            = MODE_EMA;
input ENUM_MA_METHOD    InpSlowMaMethod            = MODE_EMA;
input int               InpFastMaPeriod            = 7;
input int               InpSlowMaPeriod            = 17;
input ENUM_APPLIED_PRICE InpAppliedPrice           = PRICE_CLOSE;
input double            InpFixedLot                = 0.10;
input int               InpStopLossPoints          = 250;
input int               InpTakeProfitPoints        = 350;
input bool              InpCloseOnOppositeSignal   = true;
input bool              InpAllowLong               = true;
input bool              InpAllowShort              = true;
input bool              InpUseNewBarOnly           = true;
input int               InpMaxSpreadPoints         = 35;
input int               InpSessionStartHour        = 0;
input int               InpSessionEndHour          = 24;
input int               InpTrailingStopPoints      = 0;
input bool              InpEnableMartingale        = false;
input double            InpMartingaleMultiplier    = 2.0;
input int               InpMartingaleMaxSteps      = 3;
input bool              InpUseEconomicCalendar     = false;
input int               InpCalendarBlockMinutes    = 15;
input bool              InpUseDelayedFuturesFilter = false;
input string            InpLogFileName             = "ma_cross_baseline_trades.csv";

enum TradeSignal
{
   SIGNAL_NONE = 0,
   SIGNAL_BUY  = 1,
   SIGNAL_SELL = -1
};

int      g_fastHandle             = INVALID_HANDLE;
int      g_slowHandle             = INVALID_HANDLE;
string   g_symbol                 = "";
datetime g_lastSignalBarTime      = 0;
datetime g_lastDailyReset         = 0;
int      g_tradeCountToday        = 0;
double   g_lastClosedDealProfit   = 0.0;
int      g_martingaleStep         = 0;

string ResolveSymbol()
{
   if(StringLen(InpSymbol) > 0)
      return InpSymbol;
   return _Symbol;
}

bool IsSessionOpen(datetime when)
{
   MqlDateTime tm;
   TimeToStruct(when, tm);

   if(InpSessionStartHour == InpSessionEndHour)
      return true;

   if(InpSessionStartHour < InpSessionEndHour)
      return (tm.hour >= InpSessionStartHour && tm.hour < InpSessionEndHour);

   return (tm.hour >= InpSessionStartHour || tm.hour < InpSessionEndHour);
}

bool IsSpreadAcceptable()
{
   double point = SymbolInfoDouble(g_symbol, SYMBOL_POINT);
   if(point <= 0.0)
      return false;

   double ask = SymbolInfoDouble(g_symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(g_symbol, SYMBOL_BID);
   double spreadPoints = (ask - bid) / point;
   return (spreadPoints <= InpMaxSpreadPoints);
}

bool IsNewSignalBar()
{
   datetime times[];
   ArraySetAsSeries(times, true);
   if(CopyTime(g_symbol, InpSignalTimeframe, 0, 2, times) < 2)
      return false;

   if(!InpUseNewBarOnly)
      return true;

   if(times[0] == g_lastSignalBarTime)
      return false;

   g_lastSignalBarTime = times[0];
   return true;
}

TradeSignal GetSignal()
{
   double fast[];
   double slow[];
   ArrayResize(fast, 3);
   ArrayResize(slow, 3);
   ArraySetAsSeries(fast, true);
   ArraySetAsSeries(slow, true);

   if(CopyBuffer(g_fastHandle, 0, 0, 3, fast) < 3)
      return SIGNAL_NONE;
   if(CopyBuffer(g_slowHandle, 0, 0, 3, slow) < 3)
      return SIGNAL_NONE;

   bool crossedUp = (fast[2] <= slow[2] && fast[1] > slow[1]);
   bool crossedDown = (fast[2] >= slow[2] && fast[1] < slow[1]);

   if(crossedUp && InpAllowLong)
      return SIGNAL_BUY;
   if(crossedDown && InpAllowShort)
      return SIGNAL_SELL;
   return SIGNAL_NONE;
}

bool HasOpenPosition(ENUM_POSITION_TYPE &positionType, ulong &ticket)
{
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong positionTicket = PositionGetTicket(i);
      if(positionTicket == 0)
         continue;

      if(!PositionSelectByTicket(positionTicket))
         continue;

      string symbol = PositionGetString(POSITION_SYMBOL);
      long magic = PositionGetInteger(POSITION_MAGIC);
      if(symbol == g_symbol && magic == InpMagicNumber)
      {
         positionType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
         ticket = positionTicket;
         return true;
      }
   }

   return false;
}

ENUM_ORDER_TYPE_FILLING GetFillingMode()
{
   long fillingMode = 0;
   if(!SymbolInfoInteger(g_symbol, SYMBOL_FILLING_MODE, fillingMode))
      return ORDER_FILLING_FOK;

   if((fillingMode & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK)
      return ORDER_FILLING_FOK;
   if((fillingMode & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC)
      return ORDER_FILLING_IOC;

   return ORDER_FILLING_RETURN;
}

double GetLotSize()
{
   double volume = InpFixedLot;

   if(InpEnableMartingale && g_martingaleStep > 0)
      volume *= MathPow(InpMartingaleMultiplier, g_martingaleStep);

   double minLot = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_STEP);

   if(stepLot <= 0.0)
      stepLot = minLot;

   volume = MathMax(minLot, MathMin(maxLot, volume));
   volume = MathFloor(volume / stepLot) * stepLot;
   volume = NormalizeDouble(volume, 2);
   return volume;
}

void ResetDailyCountersIfNeeded()
{
   datetime now = TimeCurrent();
   MqlDateTime currentTm;
   MqlDateTime lastTm;
   TimeToStruct(now, currentTm);

   if(g_lastDailyReset == 0)
   {
      g_lastDailyReset = now;
      return;
   }

   TimeToStruct(g_lastDailyReset, lastTm);
   if(currentTm.year != lastTm.year || currentTm.mon != lastTm.mon || currentTm.day != lastTm.day)
   {
      g_tradeCountToday = 0;
      g_lastDailyReset = now;
   }
}

bool CalendarFilterAllowsTrade()
{
   if(!InpUseEconomicCalendar)
      return true;

   // Stub for phase 2 integration with the MQL5 economic calendar.
   return true;
}

bool FuturesFilterAllowsTrade()
{
   if(!InpUseDelayedFuturesFilter)
      return true;

   // Stub for phase 2 delayed futures filter integration.
   return true;
}

void WriteLogHeaderIfNeeded(int fileHandle)
{
   if(FileSize(fileHandle) > 0)
      return;

   FileWrite(
      fileHandle,
      "timestamp",
      "event",
      "symbol",
      "magic",
      "deal",
      "order",
      "position",
      "entry",
      "type",
      "volume",
      "price",
      "profit",
      "balance",
      "trade_count_today",
      "martingale_step",
      "comment"
   );
}

void LogEvent(
   string eventName,
   ulong dealTicket,
   ulong orderTicket,
   ulong positionTicket,
   string entryType,
   string dealType,
   double volume,
   double price,
   double profit,
   string commentText
)
{
   int fileHandle = FileOpen(InpLogFileName, FILE_READ | FILE_WRITE | FILE_CSV | FILE_SHARE_READ | FILE_COMMON);
   if(fileHandle == INVALID_HANDLE)
      return;

   WriteLogHeaderIfNeeded(fileHandle);
   FileSeek(fileHandle, 0, SEEK_END);

   FileWrite(
      fileHandle,
      TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
      eventName,
      g_symbol,
      (string)InpMagicNumber,
      (string)dealTicket,
      (string)orderTicket,
      (string)positionTicket,
      entryType,
      dealType,
      DoubleToString(volume, 2),
      DoubleToString(price, _Digits),
      DoubleToString(profit, 2),
      DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2),
      (string)g_tradeCountToday,
      (string)g_martingaleStep,
      commentText
   );

   FileClose(fileHandle);
}

bool ClosePositionByTicket(ulong ticket)
{
   if(!PositionSelectByTicket(ticket))
      return false;

   double volume = PositionGetDouble(POSITION_VOLUME);
   ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   MqlTradeRequest request = {};
   MqlTradeResult result = {};

   request.action = TRADE_ACTION_DEAL;
   request.symbol = g_symbol;
   request.magic = InpMagicNumber;
   request.position = ticket;
   request.volume = volume;
   request.deviation = InpMaxSpreadPoints;
   request.type_filling = GetFillingMode();
   request.comment = InpTradeTag;

   if(posType == POSITION_TYPE_BUY)
   {
      request.type = ORDER_TYPE_SELL;
      request.price = SymbolInfoDouble(g_symbol, SYMBOL_BID);
   }
   else
   {
      request.type = ORDER_TYPE_BUY;
      request.price = SymbolInfoDouble(g_symbol, SYMBOL_ASK);
   }

   if(!OrderSend(request, result))
   {
      PrintFormat("Failed to close position %I64u. Error=%d Retcode=%u", ticket, GetLastError(), result.retcode);
      return false;
   }

   return true;
}

bool OpenPosition(TradeSignal signal)
{
   double volume = GetLotSize();
   if(volume <= 0.0)
      return false;

   double point = SymbolInfoDouble(g_symbol, SYMBOL_POINT);
   double ask = SymbolInfoDouble(g_symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(g_symbol, SYMBOL_BID);

   double sl = 0.0;
   double tp = 0.0;
   MqlTradeRequest request = {};
   MqlTradeResult result = {};

   request.action = TRADE_ACTION_DEAL;
   request.symbol = g_symbol;
   request.magic = InpMagicNumber;
   request.volume = volume;
   request.deviation = InpMaxSpreadPoints;
   request.type_filling = GetFillingMode();
   request.comment = InpTradeTag;

   if(signal == SIGNAL_BUY)
   {
      if(InpStopLossPoints > 0)
         sl = ask - (InpStopLossPoints * point);
      if(InpTakeProfitPoints > 0)
         tp = ask + (InpTakeProfitPoints * point);

      request.type = ORDER_TYPE_BUY;
      request.price = ask;
      request.sl = sl;
      request.tp = tp;

      if(!OrderSend(request, result))
      {
         PrintFormat("Buy failed. Error=%d Retcode=%u", GetLastError(), result.retcode);
         return false;
      }
   }
   else if(signal == SIGNAL_SELL)
   {
      if(InpStopLossPoints > 0)
         sl = bid + (InpStopLossPoints * point);
      if(InpTakeProfitPoints > 0)
         tp = bid - (InpTakeProfitPoints * point);

      request.type = ORDER_TYPE_SELL;
      request.price = bid;
      request.sl = sl;
      request.tp = tp;

      if(!OrderSend(request, result))
      {
         PrintFormat("Sell failed. Error=%d Retcode=%u", GetLastError(), result.retcode);
         return false;
      }
   }
   else
   {
      return false;
   }

   return true;
}

void ApplyTrailingStop()
{
   if(InpTrailingStopPoints <= 0)
      return;

   double point = SymbolInfoDouble(g_symbol, SYMBOL_POINT);

   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;

      if(PositionGetString(POSITION_SYMBOL) != g_symbol)
         continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber)
         continue;

      ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      double currentSl = PositionGetDouble(POSITION_SL);
      double currentTp = PositionGetDouble(POSITION_TP);
      double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      double bid = SymbolInfoDouble(g_symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(g_symbol, SYMBOL_ASK);
      double newSl = currentSl;

      if(posType == POSITION_TYPE_BUY)
      {
         double candidate = bid - (InpTrailingStopPoints * point);
         if(candidate > openPrice && (currentSl == 0.0 || candidate > currentSl))
            newSl = candidate;
      }
      else if(posType == POSITION_TYPE_SELL)
      {
         double candidate = ask + (InpTrailingStopPoints * point);
         if(candidate < openPrice && (currentSl == 0.0 || candidate < currentSl))
            newSl = candidate;
      }

      if(newSl != currentSl)
      {
         MqlTradeRequest request = {};
         MqlTradeResult result = {};

         request.action = TRADE_ACTION_SLTP;
         request.symbol = g_symbol;
         request.position = ticket;
         request.sl = newSl;
         request.tp = currentTp;

         if(!OrderSend(request, result))
            PrintFormat("Trailing stop update failed for %I64u. Error=%d Retcode=%u", ticket, GetLastError(), result.retcode);
      }
   }
}

void EvaluateSignal()
{
   if(!IsNewSignalBar())
      return;
   if(!IsSessionOpen(TimeCurrent()))
      return;
   if(!IsSpreadAcceptable())
      return;
   if(!CalendarFilterAllowsTrade())
      return;
   if(!FuturesFilterAllowsTrade())
      return;

   TradeSignal signal = GetSignal();
   if(signal == SIGNAL_NONE)
      return;

   ENUM_POSITION_TYPE currentType;
   ulong currentTicket;
   bool hasPosition = HasOpenPosition(currentType, currentTicket);

   if(hasPosition)
   {
      if(signal == SIGNAL_BUY && currentType == POSITION_TYPE_BUY)
         return;
      if(signal == SIGNAL_SELL && currentType == POSITION_TYPE_SELL)
         return;

      if(!InpCloseOnOppositeSignal)
         return;

      if(!ClosePositionByTicket(currentTicket))
         return;
   }

   OpenPosition(signal);
}

int OnInit()
{
   g_symbol = ResolveSymbol();
   if(!SymbolSelect(g_symbol, true))
   {
      PrintFormat("Unable to select symbol %s", g_symbol);
      return INIT_FAILED;
   }

   if(InpFastMaPeriod <= 0 || InpSlowMaPeriod <= 0 || InpFastMaPeriod >= InpSlowMaPeriod)
   {
      Print("MA periods are invalid. Fast MA must be smaller than slow MA.");
      return INIT_PARAMETERS_INCORRECT;
   }

   g_fastHandle = iMA(g_symbol, InpSignalTimeframe, InpFastMaPeriod, 0, InpFastMaMethod, InpAppliedPrice);
   g_slowHandle = iMA(g_symbol, InpSignalTimeframe, InpSlowMaPeriod, 0, InpSlowMaMethod, InpAppliedPrice);

   if(g_fastHandle == INVALID_HANDLE || g_slowHandle == INVALID_HANDLE)
   {
      Print("Unable to create indicator handles.");
      return INIT_FAILED;
   }

   ResetDailyCountersIfNeeded();

   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_fastHandle != INVALID_HANDLE)
      IndicatorRelease(g_fastHandle);
   if(g_slowHandle != INVALID_HANDLE)
      IndicatorRelease(g_slowHandle);
}

void OnTick()
{
   ResetDailyCountersIfNeeded();
   ApplyTrailingStop();
   EvaluateSignal();
}

void OnTradeTransaction(
   const MqlTradeTransaction &trans,
   const MqlTradeRequest &request,
   const MqlTradeResult &result
)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD)
      return;

   if(!HistoryDealSelect(trans.deal))
      return;

   string symbol = HistoryDealGetString(trans.deal, DEAL_SYMBOL);
   long magic = HistoryDealGetInteger(trans.deal, DEAL_MAGIC);
   if(symbol != g_symbol || magic != InpMagicNumber)
      return;

   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   long dealType = HistoryDealGetInteger(trans.deal, DEAL_TYPE);
   double volume = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
   double price = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
   ulong orderTicket = (ulong)HistoryDealGetInteger(trans.deal, DEAL_ORDER);
   ulong positionTicket = (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
   string dealComment = HistoryDealGetString(trans.deal, DEAL_COMMENT);

   if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
   {
      g_tradeCountToday++;
      g_lastClosedDealProfit = profit;

      if(InpEnableMartingale)
      {
         if(profit < 0.0)
            g_martingaleStep = MathMin(g_martingaleStep + 1, InpMartingaleMaxSteps);
         else
            g_martingaleStep = 0;
      }

      LogEvent(
         "deal_closed",
         trans.deal,
         orderTicket,
         positionTicket,
         EnumToString((ENUM_DEAL_ENTRY)entry),
         EnumToString((ENUM_DEAL_TYPE)dealType),
         volume,
         price,
         profit,
         dealComment
      );
   }
   else
   {
      LogEvent(
         "deal_opened",
         trans.deal,
         orderTicket,
         positionTicket,
         EnumToString((ENUM_DEAL_ENTRY)entry),
         EnumToString((ENUM_DEAL_TYPE)dealType),
         volume,
         price,
         profit,
         dealComment
      );
   }
}
