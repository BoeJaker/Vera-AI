
# ------------------------------------------------------------------------
# TIME & DATE TOOLS
# ------------------------------------------------------------------------

import pytz
from datetime import datetime
from langchain_core.tools import StructuredTool
from Vera.Toolchain.schemas import TimezoneInput, TimeDeltaInput
from typing import List

class TimeTool:
    """Tool for time and date operations: get current time, calculate time deltas, and handle timezones."""

    def __init__(self, agent):
        self.agent = agent
        self.name = "TimeTool"

    def get_current_time(self, timezone: str = "UTC") -> str:
        """
        Get current date and time in specified timezone.
        Examples: UTC, America/New_York, Europe/London, Asia/Tokyo
        """
        try:
            import pytz
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            return now.strftime("%Y-%m-%d %H:%M:%S %Z")
        except ImportError:
            # Fallback if pytz not available
            now = datetime.now()
            return now.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            return f"[Error] {str(e)}"
    
    def calculate_time_delta(self, start_time: str, end_time: str = None) -> str:
        """
        Calculate time difference between two dates.
        Format: YYYY-MM-DD HH:MM:SS or YYYY-MM-DD
        If end_time not provided, uses current time.
        """
        try:
            formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]
            
            start = None
            for fmt in formats:
                try:
                    start = datetime.strptime(start_time, fmt)
                    break
                except:
                    continue
            
            if not start:
                return "[Error] Invalid start_time format"
            
            if end_time:
                end = None
                for fmt in formats:
                    try:
                        end = datetime.strptime(end_time, fmt)
                        break
                    except:
                        continue
                if not end:
                    return "[Error] Invalid end_time format"
            else:
                end = datetime.now()
            
            delta = end - start
            
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            return f"{days} days, {hours} hours, {minutes} minutes, {seconds} seconds"
            
        except Exception as e:
            return f"[Error] {str(e)}"

def add_time_tools(tool_list: List, agent) -> List:
    """
    Add time tools to the tool list.

    Call this in ToolLoader():
    ```
    tool_list = add_time_tools(tool_list, self)
    ```
    """
    tools = TimeTool(agent)

    tool_list.extend(
        [

            StructuredTool.from_function(
                func=tools.get_current_time,
                name="get_time",
                description="Get current date and time in specified timezone.",
                args_schema=TimezoneInput
            ),

            StructuredTool.from_function(
                func=tools.calculate_time_delta,
                name="time_delta",
                description="Calculate time difference between two dates or from date to now.",
                args_schema=TimeDeltaInput 
            ),

        ]
    )
    return tool_list