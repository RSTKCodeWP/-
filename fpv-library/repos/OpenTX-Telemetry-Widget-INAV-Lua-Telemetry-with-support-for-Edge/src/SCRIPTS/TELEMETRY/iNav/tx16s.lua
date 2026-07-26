-- tx16s.lua
-- iNav Horus layout adapted for RadioMaster TX16S MK3 (800x480)
-- Based on horus.lua (480x272) with layout scaled for the larger screen

local function view(data, config, modes, dir, units, labels, gpsDegMin, hdopGraph, icons, calcBearing, calcDir, VERSION, SMLCD, FILE_PATH, text, line, rect, fill, frmt)

	local rgb = data.RGB
	local SKY = rgb(0, 121, 180)
	local GROUND = rgb(98, 68, 8)
    local MAP = rgb(0, 100, 0)
	local LIGHTMAP = rgb(20, 180, 20)
	local DKGREY = rgb(48, 56, 65)
	local RIGHT_POS = 520
	local X_CNTR = 259 --(RIGHT_POS + LEFT_POS [0]) / 2 - 1
	local HEADING_DEG = 190
	local PIXEL_DEG = RIGHT_POS / HEADING_DEG
	local TOP = 20
	local BOTTOM = 276
	local Y_CNTR = 148 --(TOP + BOTTOM) / 2
	local DEGV = 280
	local CENTERED = 4
	local tmp, tmp2, top2, bot2, pitch, roll, roll1, upsideDown
	local bmap = lcd.drawBitmap
	local color = lcd.setColor
	local floor = math.floor
	local min = math.min
	local max = math.max
	local abs = math.abs
	local rad = math.rad
	local deg = math.deg
	local sin = math.sin
	local cos = math.cos
	local OYELLOW = data.RGB(255, 220, 16)
	local DEGSYM = data.etx and "°" or "@"

	-- Outlined text helper (1px black outline for contrast on HUD)
	local function otext(x, y, str, flags, col)
		local oc = data.set_flags(flags, BLACK)
		text(x + 1, y, str, oc)
		text(x - 1, y, str, oc)
		text(x, y + 1, str, oc)
		text(x, y - 1, str, oc)
		text(x, y, str, data.set_flags(flags, col))
	end

	function intersect(s1, e1, s2, e2)
		local d = (s1.x - e1.x) * (s2.y - e2.y) - (s1.y - e1.y) * (s2.x - e2.x)
		local a = s1.x * e1.y - s1.y * e1.x
		local b = s2.x * e2.y - s2.y * e2.x
		local x = (a * (s2.x - e2.x) - (s1.x - e1.x) * b) / d
		local y = (a * (s2.y - e2.y) - (s1.y - e1.y) * b) / d
		if x < min(s2.x, e2.x) - 1 or x > max(s2.x, e2.x) + 1 or y < min(s2.y, e2.y) - 1 or y > max(s2.y, e2.y) + 1 then
			return nil, nil
		end
		return floor(x + 0.5), floor(y + 0.5)
	end

	local function pitchLadder(r, adj)
		-- Scale pitch ladder rungs for larger display
		local pr = floor(r * 1.5)
		local p = sin(rad(adj)) * DEGV
		local y = (Y_CNTR - cos(rad(pitch)) * DEGV) - sin(roll1) * p
		if y > top2 and y < bot2 then
			local x = X_CNTR - cos(roll1) * p
			local xd = sin(roll1) * pr
			local yd = cos(roll1) * pr
			local x1, y1, x2, y2 = x - xd, y + yd, x + xd, y - yd
			if (y1 > top2 or y2 > top2) and (y1 < bot2 or y2 < bot2) and x1 >= 0 and x2 >= 0 then
				local lcol = r == 20 and WHITE or LIGHTGREY
				line(x1, y1, x2, y2, SOLID, data.set_flags(0, lcol))
				if r == 20 and y1 > top2 and y1 < bot2 then
				   text(x1 - 1, y1 - 8, upsideDown and -adj or adj, data.set_flags(SMLSIZE + RIGHT,data.TextColor))
				end
			end
		end
	end

	local function tics(v, p)
		tmp = floor((v + 25) * 0.1) * 10
		for i = tmp - 40, tmp, 5 do
			local tmp2 = Y_CNTR + ((v - i) * 5) - 9
			if tmp2 > TOP + 10 and tmp2 < BOTTOM - 8 then
			   line(p, tmp2 + 8, p + 3, tmp2 + 8, SOLID, data.set_flags(0, data.TextColor))
				if config[28].v == 0 and i % 10 == 0 and (i >= 0 or p > X_CNTR) and tmp2 < BOTTOM - 23 then
				   text(p + (p > X_CNTR and -2 or 6), tmp2, i, data.set_flags((p > X_CNTR and RIGHT or 0), data.TextColor))
				end
			end
		end
	end

	-- Setup: draw sky background (bg.png is 480x126, too small for 800x480 area)
	fill(0, TOP, RIGHT_POS, BOTTOM - TOP, data.set_flags(0, SKY))

	-- Calculate orientation
	if data.pitchRoll then
		pitch = (abs(data.roll) > 900 and -1 or 1) * (270 - data.pitch * 0.1) % 180
		roll = (270 - data.roll * 0.1) % 180
		upsideDown = abs(data.roll) > 900
	else
		pitch = 90 - deg(math.atan2(data.accx * (data.accz >= 0 and -1 or 1), math.sqrt(data.accy * data.accy + data.accz * data.accz)))
		roll = 90 - deg(math.atan2(data.accy * (data.accz >= 0 and 1 or -1), math.sqrt(data.accx * data.accx + data.accz * data.accz)))
		upsideDown = data.accz < 0
	end
	roll1 = rad(roll)
	top2 = config[33].v == 0 and TOP or TOP + 30
	bot2 = BOTTOM - 20
	local i = { {}, {} }
	local tl = { x = 1, y = TOP }
	local tr = { x = RIGHT_POS - 2, y = TOP }
	local bl = { x = 1, y = BOTTOM - 1 }
	local br = { x = RIGHT_POS - 2, y = BOTTOM - 1 }
	local skip = false

	-- Calculate horizon (uses simple "caged" mode for less math)
	local x = sin(roll1) * 340
	local y = cos(roll1) * 340
	local p = cos(rad(pitch)) * DEGV
	local h1 = { x = X_CNTR + x, y = Y_CNTR - y - p }
	local h2 = { x = X_CNTR - x, y = Y_CNTR + y - p }

	-- Find intersections between horizon and edges of attitude indicator
	local x1, y1 = intersect(h1, h2, tl, bl)
	local x2, y2 = intersect(h1, h2, tr, br)
	if x1 and x2 then
		i[1].x, i[1].y = x1, y1
		i[2].x, i[2].y = x2, y2
	else
		local x3, y3 = intersect(h1, h2, bl, br)
		local x4, y4 = intersect(h1, h2, tl, tr)
		if x3 and x4 then
			i[1].x, i[1].y = x3, y3
			i[2].x, i[2].y = x4, y4
		elseif (x1 or x2) and (x3 or x4) then
			i[1].x, i[1].y = x1 and x1 or x2, y1 and y1 or y2
			i[2].x, i[2].y = x3 and x3 or x4, y3 and y3 or y4
		else
			skip = true
		end
	end

	-- Draw ground
	local gflag = data.set_flags(0, GROUND)
	local fixedHorizon = config[36] ~= nil and config[36].v == 1
	if fixedHorizon then
		-- Fixed horizon: flat ground below center
		fill(tl.x, Y_CNTR, br.x - tl.x + 1, br.y - Y_CNTR + 1, gflag)
		line(tl.x, Y_CNTR, br.x, Y_CNTR, SOLID, data.set_flags(0, LIGHTGREY))
	elseif skip then
		if (pitch - 90) * (upsideDown and -1 or 1) < 0 then
		   fill(tl.x, tl.y, br.x - tl.x + 1, br.y - tl.y + 1, gflag)
		end
	else
		local trix, triy

		if upsideDown then
			trix = roll > 90 and max(i[1].x, i[2].x) or min(i[1].x, i[2].x)
			triy = min(i[1].y, i[2].y)
		else
			trix = roll > 90 and min(i[1].x, i[2].x) or max(i[1].x, i[2].x)
			triy = max(i[1].y, i[2].y)
		end

		if upsideDown then
			if triy > tl.y then
			   fill(tl.x, tl.y, br.x - tl.x + 1, triy - tl.y, gflag)
			end
			if roll > 90 and trix < br.x then
				fill(trix, triy, br.x - trix + 1, br.y - triy + 1, gflag)
			elseif roll <= 90 and trix > tl.x then
				fill(tl.x, triy, trix - tl.x, br.y - triy + 1, gflag)
			end
		else
			if triy < br.y then
				fill(tl.x, triy + 1, br.x - tl.x + 1, br.y - triy, gflag)
			end
			if roll > 90 and trix > tl.x then
				fill(tl.x, tl.y, trix - tl.x, triy - tl.y + 1, gflag)
			elseif roll <= 90 and trix < br.x then
				fill(trix, tl.y, br.x - trix + 1, triy - tl.y + 1, gflag)
			end
		end

		-- Fill remaining triangle
		local height = i[1].y - triy
		local top = i[1].y
		if height == 0 then
			height = i[2].y - triy
			top = i[2].y
		end
		local inc = 1
		if height ~= 0 then
			local width = abs(i[1].x - trix)
			local tx1 = i[1].x
			local tx2 = trix
			if width == 0 then
				width = abs(i[2].x - trix)
				tx1 = i[2].x
				tx2 = trix
			end
			inc = abs(height) < 10 and 1 or (abs(height) < 20 and 2 or ((abs(height) < width and abs(roll - 90) < 55) and 3 or 5))
			local steps = height > 0 and inc or -inc
			local slope = width / height * inc
			local s = slope > 0 and 0 or inc - 1
			slope = abs(slope) * (tx1 < tx2 and 1 or -1)
			for y = triy, top, steps do
				if abs(steps) == 1 then
				   line(tx1, y, tx2, y, SOLID, gflag)
				else
					if tx1 < tx2 then
						fill(tx1, y - s, tx2 - tx1 + 1, inc, gflag)
					else
						fill(tx2, y - s, tx1 - tx2 + 1, inc, gflag)
					end
				end
				tx1 = tx1 + slope
			end
		end

		-- Smooth horizon
		if not upsideDown and inc <= 3 then
		   if inc > 1 then
		      if inc > 2 then
			 line(i[1].x, i[1].y + 2, i[2].x, i[2].y + 2, SOLID, gflag)
		      end
		      line(i[1].x, i[1].y + 1, i[2].x, i[2].y + 1, SOLID, gflag)
		      tmpcol = SKY
		      line(i[1].x, i[1].y - 1, i[2].x, i[2].y - 1, SOLID, gflag)
		      if inc > 2 then
			 line(i[1].x, i[1].y - 2, i[2].x, i[2].y - 2, SOLID, gflag)
		      end
		      if 90 - roll > 25 then
			 line(i[1].x, i[1].y - 3, i[2].x, i[2].y - 3, SOLID, gflag)
		      end
		   end
		   gflag = data.set_flags(0, LIGHTGREY)
		   line(i[1].x, i[1].y, i[2].x, i[2].y, SOLID, gflag)
		end
	end

	-- Pitch ladder
	if data.telem then
	   tmp = pitch - 90
		if not fixedHorizon then
			local tmp2 = max(min((tmp >= 0 and floor(tmp * 0.2) or math.ceil(tmp * 0.2)) * 5, 30), -30)
			for x = tmp2 - 20, tmp2 + 20, 5 do
				if x ~= 0 and (x % 10 == 0 or (x > -30 and x < 30)) then
					pitchLadder(x % 10 == 0 and 20 or 15, x)
				end
			end
		end

		if not data.showMax then
		   text(X_CNTR - 115, Y_CNTR - 12, frmt("%.0f", upsideDown and -tmp or tmp) .. DEGSYM, data.set_flags(0 + RIGHT, data.TextColor))
		end
	end

	-- Speed & altitude tics
	tics(data.speed, 1)
	tics(data.altitude, RIGHT_POS - 5)
	if config[28].v == 0 and config[33].v == 0 then
	   text(68, TOP + 2, units[data.speed_unit], data.set_flags(0, data.TextColor))
	   text(RIGHT_POS - 70, TOP + 2, "Alt " .. units[data.alt_unit], data.set_flags(RIGHT, data.TextColor))
	elseif config[28].v > 0 then
	   local smrf = data.set_flags(RIGHT, data.TextColor)
	   text(68, Y_CNTR - 30, units[data.speed_unit], smrf)
	   text(RIGHT_POS - 10, Y_CNTR - 30, "Alt " .. units[data.alt_unit], smrf)
	end
	-- Compass
	if data.showHead then
		for i = 0, 348.75, 11.25 do
			tmp = floor(((i - data.heading + (361 + HEADING_DEG * 0.5)) % 360) * PIXEL_DEG - 2.5)
			if tmp >= 9 and tmp <= RIGHT_POS - 12 then
				if i % 45 == 0 then
				   local idx = math.floor(i / 45 + 0.5)
				   local lbl = dir[idx] or (i == 180 and "S" or "")
				   otext(tmp, bot2, lbl, CENTERED, data.TextColor)
				else
				   line(tmp, BOTTOM - 5, tmp, BOTTOM - 1, SOLID, data.set_flags(0, data.TextColor))
				end
			end
		end
	end

	-- Calculate the maximum distance for scaling home location and map
	local maxDist = max(min(data.distanceMax, data.distanceLast * 6), data.distRef * 10)

	-- Home direction
	if data.showHead and data.armed and data.telem and data.gpsHome ~= false then
	   if data.distanceLast >= data.distRef then
			local bearing = calcBearing(data.gpsHome, data.gpsLatLon) + 540 % 360
			if config[15].v == 1 then
				-- HUD method
				local d = 1 - data.distanceLast / maxDist
				local w = HEADING_DEG / (d + 1)
				local h = floor((((upsideDown and data.heading - bearing or bearing - data.heading) + (361 + w * 0.5)) % 360) * (RIGHT_POS / w) - 0.5)
				local p = sin(math.atan(data.altitude / data.distanceLast * 0.5)) * (upsideDown and DEGV or -DEGV)
				local x = (X_CNTR - cos(roll1) * p) + (sin(roll1) * (h - X_CNTR)) - 9
				local y = ((Y_CNTR - cos(rad(pitch)) * DEGV) - sin(roll1) * p) - (cos(roll1) * (h - X_CNTR)) - 9
				if x >= 0 and x < RIGHT_POS - 17 then
					local s = floor(d * 2 + 0.5)
					bmap(icons.home[s], x, min(max(y, s == 2 and TOP or 15), BOTTOM - (s == 2 and 35 or 30)))
				end
			else
				-- Bottom-fixed method
				local home = floor(((bearing - data.heading + (361 + HEADING_DEG * 0.5)) % 360) * PIXEL_DEG - 2.5)
				if home >= 3 and home <= RIGHT_POS - 6 then
					bmap(icons.home[1], home - 7, BOTTOM - 31)
				end
			end
		end
		-- Flight path vector
		if data.fpv_id > -1 and data.speed >= 8 then
			tmp = (data.fpv - data.heading + 360) % 360
			if tmp >= 302 or tmp <= 57 then
				local fpv = floor(((data.fpv - data.heading + (361 + HEADING_DEG * 0.5)) % 360) * PIXEL_DEG - 0.5)
				local p = sin(data.vspeed_id == -1 and rad(pitch - 90) or (math.tan(data.vspeed / (data.speed * (data.speed_unit == 8 and 1.4667 or 0.2778))))) * DEGV
				local x = (X_CNTR - cos(roll1) * p) + (sin(roll1) * (fpv - X_CNTR)) - 9
				local y = ((Y_CNTR - cos(rad(pitch)) * DEGV) - sin(roll1) * p) - (cos(roll1) * (fpv - X_CNTR)) - 6
				if y > TOP and y < bot2 and x >= 0 then
					bmap(icons.fpv, x, y)
				end
			end
		end
	end

	-- Aircraft reference mark
	do
		local ycol = data.set_flags(0, OYELLOW)
		if fixedHorizon then
			-- Fixed horizon mode: aircraft symbol moves with pitch/roll
			local py = Y_CNTR - (pitch - 90) * DEGV / 90
			py = max(TOP + 15, min(BOTTOM - 15, py))
			local r = rad(roll - 90)
			local s, c = sin(r), cos(r)
			local wing = 70
			local gap = 15
			local oc = data.set_flags(0, BLACK)
			-- Wing bars: perpendicular-offset lines for thickness (7px: 5 yellow + 2 black outline)
			for d = -3, 3 do
				local col = (d > -3 and d < 3) and ycol or oc
				local ox, oy = -s * d, c * d
				line(X_CNTR - c * wing + ox, py + s * wing + oy, X_CNTR - c * gap + ox, py + s * gap + oy, SOLID, col)
				line(X_CNTR + c * gap + ox, py - s * gap + oy, X_CNTR + c * wing + ox, py - s * wing + oy, SOLID, col)
			end
			-- Tail (points up from center when level)
			local tail = 25
			for d = -2, 2 do
				local col = (d > -2 and d < 2) and ycol or oc
				line(X_CNTR, py + d, X_CNTR - s * tail, py - c * tail + d, SOLID, col)
			end
			-- Center dot
			fill(X_CNTR - 4, py - 4, 9, 9, oc)
			fill(X_CNTR - 3, py - 3, 7, 7, ycol)
		else
			-- Standard mode: fixed aircraft symbol at center
			local fgv = config[30].v
			if fgv <= 3 then
				-- Wing lines (types 0-3 have horizontal wings with 2px thickness)
				local wcol = fgv <= 1 and ycol or data.set_flags(0, BLACK)
				line(X_CNTR - 90, Y_CNTR, X_CNTR - 15, Y_CNTR, SOLID, wcol)
				line(X_CNTR - 90, Y_CNTR + 1, X_CNTR - 15, Y_CNTR + 1, SOLID, wcol)
				line(X_CNTR + 15, Y_CNTR, X_CNTR + 90, Y_CNTR, SOLID, wcol)
				line(X_CNTR + 15, Y_CNTR + 1, X_CNTR + 90, Y_CNTR + 1, SOLID, wcol)
			end
			if fgv == 0 then
				-- Small black dot
				fill(X_CNTR - 2, Y_CNTR - 2, 5, 5, data.set_flags(0, BLACK))
			elseif fgv == 1 then
				-- Yellow dot
				fill(X_CNTR - 2, Y_CNTR - 2, 5, 5, ycol)
			elseif fgv == 2 then
				-- Larger chevron/arrowhead (yellow fill, black outline)
				for dy = 0, 13 do
					local hw = floor(dy * 1.15 + 0.5)
					if hw > 0 then
						fill(X_CNTR - hw, Y_CNTR - 8 + dy, hw * 2 + 1, 1, ycol)
					end
				end
				local oc = data.set_flags(0, BLACK)
				line(X_CNTR, Y_CNTR - 8, X_CNTR - 15, Y_CNTR + 5, SOLID, oc)
				line(X_CNTR, Y_CNTR - 8, X_CNTR + 15, Y_CNTR + 5, SOLID, oc)
			elseif fgv == 3 then
				-- Smaller chevron
				for dy = 0, 9 do
					local hw = floor(dy * 1.1 + 0.5)
					if hw > 0 then
						fill(X_CNTR - hw, Y_CNTR - 5 + dy, hw * 2 + 1, 1, ycol)
					end
				end
				local oc = data.set_flags(0, BLACK)
				line(X_CNTR, Y_CNTR - 5, X_CNTR - 10, Y_CNTR + 4, SOLID, oc)
				line(X_CNTR, Y_CNTR - 5, X_CNTR + 10, Y_CNTR + 4, SOLID, oc)
			elseif fgv == 4 then
				-- Crosshair with center rectangle
				line(X_CNTR - 15, Y_CNTR, X_CNTR - 6, Y_CNTR, SOLID, ycol)
				line(X_CNTR + 6, Y_CNTR, X_CNTR + 15, Y_CNTR, SOLID, ycol)
				line(X_CNTR, Y_CNTR - 15, X_CNTR, Y_CNTR - 6, SOLID, ycol)
				line(X_CNTR, Y_CNTR + 6, X_CNTR, Y_CNTR + 15, SOLID, ycol)
				rect(X_CNTR - 5, Y_CNTR - 5, 11, 11, ycol)
			elseif fgv == 5 then
				-- W-wing / zigzag (2px thick)
				line(X_CNTR - 50, Y_CNTR - 8, X_CNTR - 20, Y_CNTR + 6, SOLID, ycol)
				line(X_CNTR - 20, Y_CNTR + 6, X_CNTR, Y_CNTR - 2, SOLID, ycol)
				line(X_CNTR, Y_CNTR - 2, X_CNTR + 20, Y_CNTR + 6, SOLID, ycol)
				line(X_CNTR + 20, Y_CNTR + 6, X_CNTR + 50, Y_CNTR - 8, SOLID, ycol)
				line(X_CNTR - 50, Y_CNTR - 7, X_CNTR - 20, Y_CNTR + 7, SOLID, ycol)
				line(X_CNTR - 20, Y_CNTR + 7, X_CNTR, Y_CNTR - 1, SOLID, ycol)
				line(X_CNTR, Y_CNTR - 1, X_CNTR + 20, Y_CNTR + 7, SOLID, ycol)
				line(X_CNTR + 20, Y_CNTR + 7, X_CNTR + 50, Y_CNTR - 7, SOLID, ycol)
			end
		end
	end

	-- Speed & altitude readouts (MIDSIZE with outline for 800x480)
	tmp = data.showMax and data.speedMax or data.speed
	local telemCol = data.telem and data.TextColor or RED
    fill(0, Y_CNTR - 10, 65, 30, data.set_flags(0, DKGREY))
	rect(0, Y_CNTR - 10, 65, 30, data.set_flags(0, WHITE))
	otext(62, Y_CNTR - 16, tmp >= 99.5 and floor(tmp + 0.5) or frmt("%.1f", tmp), MIDSIZE + RIGHT, telemCol)

	tmp = data.showMax and data.altitudeMax or data.altitude
    fill(RIGHT_POS - 67, Y_CNTR - 10, 67, 30, data.set_flags(0, DKGREY))
	rect(RIGHT_POS - 67, Y_CNTR - 10, 67, 30, data.set_flags(0, WHITE))
	otext(RIGHT_POS - 2, Y_CNTR - 16, floor(tmp + 0.5), MIDSIZE + RIGHT, ((not data.telem or tmp + 0.5 >= config[6].v) and RED or data.TextColor))
	if data.altHold then
		bmap(icons.lock, RIGHT_POS - 80, Y_CNTR - 7)
	end

	-- Heading
	if data.showHead then
        fill(X_CNTR - 42, bot2 - 18, 72, 30, data.set_flags(0, DKGREY))
		rect(X_CNTR - 42, bot2 - 18, 72, 30, data.set_flags(0, WHITE))
		otext(X_CNTR + 30, bot2 - 24, floor(data.heading + 0.5) % 360 .. DEGSYM, MIDSIZE + RIGHT, telemCol)
	end

	-- Roll scale (scale bitmap for larger display)
	if config[33].v == 1 then
		bmap(icons.roll, 125, 20, 150)
		if roll > 30 and roll < 150 and not upsideDown then
			local x1, y1, x2, y2, x3, y3 = calcDir(rad(roll - 90), rad(roll + 55), rad(roll - 235), X_CNTR - (cos(roll1) * 120), 110 - (sin(roll1) * 60), 10)
			local ycol = data.set_flags(0, OYELLOW)
			line(x1, y1, x2, y2, SOLID, ycol)
			line(x1, y1, x3, y3, SOLID, ycol)
			line(x2, y2, x3, y3, SOLID, ycol)
		end
	end

	-- Variometer
	if config[7].v % 2 == 1 then
		fill(RIGHT_POS, TOP, 14, BOTTOM - TOP, data.set_flags(0, DKGREY))
		line(RIGHT_POS + 14, TOP, RIGHT_POS + 14, BOTTOM - 1, SOLID, data.set_flags(0, LIGHTGREY))
		line(RIGHT_POS, Y_CNTR - 1, RIGHT_POS + 13, Y_CNTR - 1, SOLID, data.set_flags(0, GREY))
		if data.telem then
		   tmp = math.log(1 + min(abs(0.6 * (data.vspeed_unit == 6 and data.vspeed * 0.3048 or data.vspeed)), 10)) * (data.vspeed < 0 and -1 or 1)
		   local y1 = Y_CNTR - (tmp * 0.416667 * (Y_CNTR - 21))
		   local y2 = Y_CNTR - (tmp * 0.384615 * (Y_CNTR - 21))
		   local ycol = data.set_flags(0, OYELLOW)
		   line(RIGHT_POS, y1 - 1, RIGHT_POS + 13, y2 - 1, SOLID, ycol)
		   line(RIGHT_POS, y1, RIGHT_POS + 13, y2, SOLID, ycol)
		end
		if data.startup == 0 then
		   text(RIGHT_POS + 17, TOP + 2, frmt(abs(data.vspeed) >= 9.95 and "%.0f" or "%.1f", data.vspeed) .. units[data.vspeed_unit], data.set_flags(0, telemCol))
		end
	end

	-- Calc orientation
	tmp = data.headingRef
	if data.showDir or data.headingRef == -1 then
		tmp = 0
	end
	local r1 = rad(data.heading - tmp)
	local r2 = rad(data.heading - tmp + 145)
	local r3 = rad(data.heading - tmp - 145)

	-- Radar
	local LEFT_POS = RIGHT_POS + (config[7].v % 2 == 1 and 15 or 0)
	RIGHT_POS = 799

    fill(LEFT_POS, TOP, RIGHT_POS, BOTTOM -TOP, data.set_flags(0, MAP))

	X_CNTR = (RIGHT_POS + LEFT_POS) * 0.5 - 1
	if data.startup == 0 then
		-- Launch/north-based orientation
		if data.showDir or data.headingRef == -1 then
		   text(LEFT_POS + 4, Y_CNTR - 9, dir[6], data.set_flags(0, data.TextColor))
		   text(RIGHT_POS - 3, Y_CNTR - 9, dir[2], data.set_flags(RIGHT, data.TextColor))
		end
		local cx, cy, d

		-- Altitude graph
		if config[28].v > 0 then
		   local mcol = data.set_flags(0,LIGHTMAP)
		   local factor = 60 / (data.altMax - data.altMin)
			for i = 1, 60 do
				cx = RIGHT_POS - 60 + i
				cy = floor(BOTTOM - (data.alt[((data.altCur - 2 + i) % 60) + 1] - data.altMin) * factor + 0.5)
				if cy < BOTTOM then
				   line(cx, cy, cx, BOTTOM - 1, SOLID, mcol)
				end
				if (i - 1) % (60 / config[28].v) == 0 then
				   mcol = data.set_flags(0, DKGREY)
				   line(cx, BOTTOM - 60, cx, BOTTOM - 1, DOTTED, mcol)
				   mcol = data.set_flags(0, LIGHTMAP)
				end
			end
			if data.altMin < -1 then
				cy = BOTTOM - (-data.altMin * factor)
				mcol = data.set_flags(0,LIGHTMAP)
				line(RIGHT_POS - 58, cy, RIGHT_POS - 1, cy, DOTTED, mcol)
				if cy < BOTTOM - 10 then
				   text(RIGHT_POS - 59, cy - 8, "0", data.set_flags(SMLSIZE + RIGHT,data.TextColor))
				end
			end
			text(RIGHT_POS - 3, BOTTOM - 76, floor(data.altMax + 0.5) .. units[data.alt_unit], data.set_flags(SMLSIZE + RIGHT, data.TextColor))
		end

		if data.gpsHome ~= false then
			-- Craft location
			tmp2 = config[31].v == 1 and 60 or 120
			d = data.distanceLast >= data.distRef and min(max(data.distanceLast / maxDist * tmp2, 7), tmp2) or 1
			local bearing = calcBearing(data.gpsHome, data.gpsLatLon) - tmp
			local rad1 = rad(bearing)
			cx = floor(sin(rad1) * d + 0.5)
			cy = floor(cos(rad1) * d + 0.5)
			-- Home position
			local hx = X_CNTR + 2
			local hy = Y_CNTR
			if config[31].v ~= 1 then
				hx = hx - (d > 9 and cx * 0.5 or 0)
				hy = hy + (d > 9 and cy * 0.5 or 0)
			end
			if d >= 12 then
				bmap(icons.home[1], hx - 8, hy - 10)
			elseif d > 1 then
			   fill(hx - 1, hy - 1, 3, 3, SOLID, data.set_flags(0, data.TextColor))
			end
			-- Shift craft location
			cx = d == 1 and X_CNTR + 2 or cx + hx
			cy = d == 1 and Y_CNTR or hy - cy
		else
			cx = X_CNTR + 2
			cy = Y_CNTR
			d = 1
		end
		-- Orientation
		local x1, y1, x2, y2, x3, y3 = calcDir(r1, r2, r3, cx, cy, 16)
		line(x2, y2, x3, y3, SOLID, data.set_flags(0, LIGHTGREY))
		local tcol = data.set_flags(0, data.TextColor)
		line(x1, y1, x2, y2, SOLID, tcol)
		line(x1, y1, x3, y3, SOLID, tcol)
		tmp = data.distanceLast < 1000 and floor(data.distanceLast + 0.5) .. units[data.dist_unit] or (frmt("%.1f", data.distanceLast / (data.dist_unit == 9 and 1000 or 5280)) .. (data.dist_unit == 9 and "km" or "mi"))
		text(LEFT_POS + 4, BOTTOM - 26, tmp, data.set_flags(0, telemCol))
	end

	-- Startup message
	if data.startup == 2 then
	   local tcol = data.set_flags(MIDSIZE, BLACK)
	   text(X_CNTR - 78, 100, "Lua Telemetry", tcol)
	   text(X_CNTR - 38, 135, "v" .. VERSION, tcol)
	   tcol = data.set_flags(MIDSIZE, data.TextColor)
	   text(X_CNTR - 79, 99, "Lua Telemetry", tcol)
	   text(X_CNTR - 39, 134, "v" .. VERSION, tcol)
	end

	-- Data section (bottom panel) — 800px wide, ~200px tall
	local X1 = 200
	local X2 = 400
	local X3 = 600
	TOP = BOTTOM + 1
	BOTTOM = 479

	-- Box 1 (fuel, battery, rssi)
	tmp = (not data.telem or data.cell < config[3].v or (data.showFuel and config[23].v == 0 and data.fuel <= config[17].v)) and RED or data.TextColor
	if data.showFuel then
		if config[23].v > 0 or (data.crsf and data.showMax) then
		   text(X1, TOP + 2, (data.crsf and data.fuelRaw or data.fuel) .. data.fUnit[data.crsf and 1 or config[23].v], data.set_flags(MIDSIZE + RIGHT, tmp))
		else
		   text(X1 - 3, TOP + 2, data.fuel .. "%", data.set_flags(MIDSIZE + RIGHT, tmp))
			if data.fl ~= data.fuel then
				local red = data.fuel >= config[18].v and max(floor((100 - data.fuel) / (100 - config[18].v) * 255), 0) or 255
				local green = data.fuel < config[18].v and max(floor((data.fuel - config[17].v) / (config[18].v - config[17].v) * 255), 0) or 255
				data.fc = rgb(red, green, 60)
				data.fl = data.fuel
			end
			lcd.drawGauge(0, TOP + 40, X1 - 3, 18, min(data.fuel, 99), 100, data.set_flags(0, data.fc))
		end
		text(0, TOP + ((config[23].v > 0 or (data.crsf and data.showMax)) and 26 or 12), labels[1], data.set_flags(0, data.TextColor))
	end

	local val = math.floor((data.showMax and data.cellMin or data.cell) * 100 + 0.5) * 0.01
	text(X1, TOP + 62, frmt(config[1].v == 0 and "%.2fV" or "%.1fV", config[1].v == 0 and val or (data.showMax and data.battMin or data.batt)), data.set_flags(MIDSIZE + RIGHT,tmp))
	text(0, TOP + 72, labels[2], data.set_flags(0, data.TextColor))
	if data.bl ~= val then
		local red = val >= config[2].v and max(floor((4.2 - val) / (4.2 - config[2].v) * 255), 0) or 255
		local green = val < config[2].v and max(floor((val - config[3].v) / (config[2].v - config[3].v) * 255), 0) or 255
		data.bc = rgb(red, green, 60)
		data.bl = val
	end
	lcd.drawGauge(0, TOP + 102, X1, 18, min(max(val - config[3].v + 0.1, 0) * (100 / (4.2 - config[3].v + 0.1)), 99), 100, data.set_flags(0,data.bc))

	tmp = (not data.telem or data.rssi < data.rssiLow) and RED or data.TextColor
	val = data.showMax and data.rssiMin or data.rssiLast
	text(X1, TOP + 122, val .. (data.crsf and "%" or "dB"), data.set_flags(MIDSIZE + RIGHT,tmp))
	text(0, TOP + 130, data.crsf and "LQ" or "RSSI", data.set_flags(0, data.TextColor))
	if data.rl ~= val then
		local red = val >= data.rssiLow and max(floor((100 - val) / (100 - data.rssiLow) * 255), 0) or 255
		local green = val < data.rssiLow and max(floor((val - data.rssiCrit) / (data.rssiLow - data.rssiCrit) * 255), 0) or 255
		data.rc = rgb(red, green, 60)
		data.rl = val
	end
	lcd.drawGauge(0, TOP + 162, X1, 18, min(val, 99), 100, data.set_flags(0, data.rc))

	-- Box 2 (altitude, distance, current)
	tmp = data.showMax and data.altitudeMax or data.altitude
	text(X1 + 16, TOP + 18, labels[4], data.set_flags(0, data.TextColor))
	text(X2, TOP + 30, floor(tmp + 0.5) .. units[data.alt_unit], data.set_flags(MIDSIZE + RIGHT,((not data.telem or tmp + 0.5 >= config[6].v) and RED or data.TextColor)))
	tmp2 = data.showMax and data.distanceMax or data.distanceLast
	tmp = tmp2 < 1000 and floor(tmp2 + 0.5) .. units[data.dist_unit] or (frmt("%.1f", tmp2 / (data.dist_unit == 9 and 1000 or 5280)) .. (data.dist_unit == 9 and "km" or "mi"))
	text(X1 + 16, TOP + 66, labels[5], data.set_flags(0, data.TextColor))
	text(X2, TOP + 82, tmp, data.set_flags(MIDSIZE + RIGHT, telemCol))
	if data.showCurr then
		tmp = data.showMax and data.currentMax or data.current
		text(X1 + 16, TOP + 120, labels[3], data.set_flags(0, data.TextColor))
		text(X2, TOP + 134, (tmp >= 99.5 and floor(tmp + 0.5) or frmt("%.1fA", tmp)), data.set_flags(MIDSIZE + RIGHT, telemCol))
	end

	-- Box 3 (flight modes, orientation)
	tmp = (X2 + X3) * 0.5 + 4
	text(tmp, TOP + 2, modes[data.modeId].t, data.set_flags(CENTERED, (modes[data.modeId].f == 3 and data.WarningColor or data.TextColor)))
	if data.altHold then
		bmap(icons.lock, X1 + 108, TOP + 6)
	end
	if data.headFree then
	   text(X2 + 10, TOP + 24, "HF", data.set_flags(0, RED))
	end

	if data.showHead then
		if data.showDir or data.headingRef == -1 then
		   text(tmp, TOP + 22, dir[0], data.set_flags(CENTERED, data.TextColor))
		   text(X3 - 6, TOP + 120, dir[2], data.set_flags(RIGHT, data.TextColor))
		   text(X2 + 14, TOP + 120, dir[6], data.set_flags(0, data.TextColor))
           text(tmp + 4, BOTTOM - 26, floor(data.heading + 0.5) % 360 .. DEGSYM, data.set_flags(CENTERED, telemCol))
		end
		local compassY = TOP + 125
		local x1, y1, x2, y2, x3, y3 = calcDir(r1, r2, r3, tmp, compassY, 45)
		if data.headingHold then
		   fill((x2 + x3) * 0.5 - 2, (y2 + y3) * 0.5 - 2, 5, 5, SOLID, data.set_flags(0,data.TextColor))
		else
		   line(x2, y2, x3, y3, SOLID, data.set_flags(0, data.TextColor))
		end
		local tcol = data.set_flags(0, data.TextColor)
		line(x1, y1, x2, y2, SOLID, tcol)
		line(x1, y1, x3, y3, SOLID, tcol)
	end

	-- Box 4 (GPS info, speed)
	if data.crsf then
		if data.tpwr then
		   text(RIGHT_POS - 4, TOP + 2, data.tpwr .. "mW", data.set_flags(RIGHT + MIDSIZE, telemCol))
		end
		text(RIGHT_POS - 4, TOP + 34, data.satellites % 100, data.set_flags(MIDSIZE + RIGHT, telemCol))
	else
		tmp = ((data.armed or data.modeId == 6) and data.hdop < 11 - config[21].v * 2) or not data.telem
		text(X3 + 60, TOP + 2, (data.hdop == 0 and not data.gpsFix) and "-- --" or (9 - data.hdop) * 0.5 + 0.8, data.set_flags(MIDSIZE + RIGHT, (tmp and RED or data.TextColor)))
		     text(X3 + 14, TOP + 30, "HDOP", data.set_flags(0, data.TextColor))
		     text(RIGHT_POS - 3, TOP + 2, data.satellites % 100, data.set_flags(MIDSIZE + RIGHT, telemCol))
	end
	hdopGraph(X3 + 80, TOP + (data.crsf and 62 or 30))
	tmp = ((not data.telem or not data.gpsFix) and RED or data.TextColor)
	if not data.crsf then
	   text(RIGHT_POS - 4, TOP + 34, floor(data.gpsAlt + 0.5) .. (data.gpsAlt_unit == 10 and "'" or units[data.gpsAlt_unit]), data.set_flags(MIDSIZE+RIGHT, tmp))
	end
	local pcol = data.set_flags(RIGHT, tmp)
	text(RIGHT_POS - 4, TOP + 66, config[16].v == 0 and frmt("%.6f", data.gpsLatLon.lat) or gpsDegMin(data.gpsLatLon.lat, true), pcol)
	text(RIGHT_POS - 4, TOP + 90, config[16].v == 0 and frmt("%.6f", data.gpsLatLon.lon) or gpsDegMin(data.gpsLatLon.lon, false), pcol)
	tmp = data.showMax and data.speedMax or data.speed
	text(RIGHT_POS - 4, TOP + 122, tmp >= 99.5 and floor(tmp + 0.5) .. units[data.speed_unit] or frmt("%.1f", tmp) .. units[data.speed_unit], data.set_flags(MIDSIZE + RIGHT, telemCol))

	-- Dividers
	local dkgcol = data.set_flags(0, DKGREY)
	line(X1 + 3, TOP, X1 + 3, BOTTOM, SOLID, dkgcol)
	line(X2 + 3, TOP, X2 + 3, BOTTOM, SOLID, dkgcol)
	line(X3 + 3, TOP, X3 + 3, BOTTOM, SOLID, dkgcol)
	line(X3 + 3, TOP + 118, RIGHT_POS, TOP + 118, SOLID, dkgcol)
	if data.crsf then
		line(X3 + 3, TOP + 34, RIGHT_POS, TOP + 34, SOLID, dkgcol)
	end
	line(0, TOP - 1, LCD_W - 1, TOP - 1, SOLID, data.set_flags(0, LIGHTGREY))

	if data.showMax then
		fill(310, TOP - 24, 100, 24, data.set_flags(0, OYELLOW))
		text(405, TOP - 24, "Min/Max", data.set_flags(RIGHT, BLACK))
	end
end

return view
