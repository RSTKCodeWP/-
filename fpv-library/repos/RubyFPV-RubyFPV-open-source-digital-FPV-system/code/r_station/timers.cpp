#include "timers.h"

// Globals

u32 g_TimeLastPeriodicCheck = 0;

// RC Tx
u32 g_TimeLastFPSCalculation = 0;
u32 g_TimeLastJoystickCheck = 0;

// Router
u32 g_TimeLastControllerLinkStatsSent = 0;

u32 g_TimeLastSetRadioFlagsCommandSent = 0;
u32 g_TimeLastVideoParametersOrProfileChanged = 0;
u32 g_uTimeLastNegociateRadioPacket = 0;

bool isNegociatingRadioLink()
{
   if ( g_TimeNow < g_uTimeLastNegociateRadioPacket + 4000 )
      return true;
   return false;
}