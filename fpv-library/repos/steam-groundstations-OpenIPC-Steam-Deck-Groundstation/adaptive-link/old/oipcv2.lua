local received_text = ""
local process_text = ""
local rx_data = ""
local start = 0
local stop = 0
local tmp =0
local gVal1 = 0
local i = 1

function split(str, character)
  result = {}

  index = 1
  for s in string.gmatch(str, "[^"..character.."]+") do
    result[index] = s
    index = index + 1
  end
  return result
end

function count(base, pattern)
    return select(2, string.gsub(base, pattern, ""))
end


local function init()
  -- Called once when the script is loaded
  --setSerialBaudrate(9600)
  setSerialBaudrate(115200)
  
  
    startTime=getTime()
    wait=20
    waitTime=startTime+wait
  
end

local function run()
  -- Called periodically while the Special Function switch is on 
    local received_text = ""
    local process_text = ""
    local rx_data = ""
    --main loop runs every "wait" time 500=5sec
    
    startTime=getTime()
    if startTime > waitTime then
      start = 0
      stop = 0
      --serialWrite("RUN")
    
    
        -- Read serial data buffer
    rx_data = serialRead()
    if rx_data ~= "" then
    --serialWrite("Old buffer: " .. received_text)
    received_text = rx_data
    --serialWrite("New buffer: " .. received_text)
    
    --find position for first /
    start, tmp = string.find(received_text, "/")
    --find position for last
    stop = string.find(received_text, "/[^/]*$")
    
    --stop = stop
    
    if start == nil then
    --serialWrite("Start is nil")
    end
    --serialWrite("Start: " .. start)
    --serialWrite("Stop: " .. stop)
    
      -- check if data has been sent between separators
      
      --serialWrite(" len: " .. string.len(received_text))
      if start ~= nil and stop > (start+1) then
        --there is text to split
        process_text = string.sub(received_text, start, stop)
        --received_text = string.sub(received_text, stop, string.len(received_text))
        received_text = ""
        --serialWrite("drop on extra chars: " .. received_text)
      end
    
     -- check if there is process_text data, text between at least two separators
     -- ADDED NEW CONDITION TOESCAPE ALL /////// (Count), to be tested
      if stop ~= nil and start ~= nil and stop > (start+1) and stop > count(received_text,"/") then
      --serialWrite("Found pattern: " .. process_text)
      
      -- split out the data between separators
      process_arr = split(process_text, "/")
      --serialWrite("Process_arr1: " .. process_arr[1])
      
      i = 1
      while process_arr[i] ~= nil do
        -- debug code
        -- the last index in table is a empty string
        if process_arr[i] ~= "" then
        --serialWrite("Arr" .. i .. ": " .. process_arr[i] .. "\r")
      
        if type(tonumber(process_arr[i])) == "number" then
          serialWrite("NumOK+" .. process_arr[i])      
          
          if tonumber(process_arr[i]) >= -1024 and tonumber(process_arr[i]) <= 1024 then
            model.setGlobalVariable(0, 0, tonumber(process_arr[i]))
          end
        
        else
          serialWrite("NAN+" .. process_arr[i])
        end
        
        
      
      
      end
      
      i = i + 1
      end
 
      end
    
    
    
    
  end
  startTime=getTime()
  waitTime=startTime+wait
  end

end

local function background()
  -- Called periodically while the Special Function switch is off
  --Just empty the buffer and do nothing else
  startTime=getTime()
  if startTime > waitTime then
    rx_data = serialRead()
    startTime=getTime()
    waitTime=startTime+wait
  end

end

return { run=run, background=background, init=init }
