// Divine JSON Parser Library
// Simple JSON parsing - Terry's way
// No bloat, just essentials

// Find JSON value by key
U8 *JSONGetString(U8 *json, U8 *key) {
  // Find "key":"value" pattern
  U8 *search_pattern = StrFormat("\"%s\":\"", key);
  I64 pos = StrFind(json, search_pattern);
  
  if (pos == -1) return "";
  
  // Move to start of value
  pos += StrLen(search_pattern);
  
  // Find end quote
  I64 end = pos;
  while (json[end] != '"' && json[end] != 0) {
    if (json[end] == '\\') end++; // Skip escaped chars
    end++;
  }
  
  return StrSubstr(json, pos, end);
}

// Get integer value
I64 JSONGetInt(U8 *json, U8 *key) {
  U8 *search_pattern = StrFormat("\"%s\":", key);
  I64 pos = StrFind(json, search_pattern);
  
  if (pos == -1) return 0;
  
  pos += StrLen(search_pattern);
  
  // Skip whitespace
  while (json[pos] == ' ' || json[pos] == '\t') pos++;
  
  return StrToI64(json + pos);
}

// Get boolean value
Bool JSONGetBool(U8 *json, U8 *key) {
  U8 *search_pattern = StrFormat("\"%s\":", key);
  I64 pos = StrFind(json, search_pattern);
  
  if (pos == -1) return FALSE;
  
  pos += StrLen(search_pattern);
  
  // Skip whitespace
  while (json[pos] == ' ' || json[pos] == '\t') pos++;
  
  if (StrNCmp(json + pos, "true", 4) == 0) return TRUE;
  return FALSE;
}

// Check if key exists
Bool JSONHasKey(U8 *json, U8 *key) {
  U8 *search_pattern = StrFormat("\"%s\":", key);
  return StrFind(json, search_pattern) != -1;
}

// Extract array element by index
U8 *JSONGetArrayElement(U8 *json, I64 index) {
  I64 pos = 0;
  I64 current_index = 0;
  I64 depth = 0;
  Bool in_string = FALSE;
  
  // Find array start
  while (json[pos] != '[' && json[pos] != 0) pos++;
  if (json[pos] == 0) return "";
  
  pos++; // Skip '['
  
  I64 element_start = pos;
  
  while (json[pos] != 0) {
    if (json[pos] == '"' && json[pos-1] != '\\') {
      in_string = !in_string;
    }
    
    if (!in_string) {
      if (json[pos] == '{' || json[pos] == '[') {
        depth++;
      } else if (json[pos] == '}' || json[pos] == ']') {
        depth--;
        if (depth < 0) break; // End of array
      } else if (json[pos] == ',' && depth == 0) {
        if (current_index == index) {
          return StrSubstr(json, element_start, pos);
        }
        current_index++;
        element_start = pos + 1;
      }
    }
    
    pos++;
  }
  
  // Last element
  if (current_index == index) {
    return StrSubstr(json, element_start, pos);
  }
  
  return "";
}

// Count array elements
I64 JSONArrayLength(U8 *json) {
  I64 pos = 0;
  I64 count = 0;
  I64 depth = 0;
  Bool in_string = FALSE;
  
  // Find array start
  while (json[pos] != '[' && json[pos] != 0) pos++;
  if (json[pos] == 0) return 0;
  
  pos++; // Skip '['
  
  // Empty array check
  while (json[pos] == ' ' || json[pos] == '\t' || json[pos] == '\n') pos++;
  if (json[pos] == ']') return 0;
  
  count = 1; // At least one element
  
  while (json[pos] != 0) {
    if (json[pos] == '"' && json[pos-1] != '\\') {
      in_string = !in_string;
    }
    
    if (!in_string) {
      if (json[pos] == '{' || json[pos] == '[') {
        depth++;
      } else if (json[pos] == '}' || json[pos] == ']') {
        depth--;
        if (depth < 0) break;
      } else if (json[pos] == ',' && depth == 0) {
        count++;
      }
    }
    
    pos++;
  }
  
  return count;
}

// Build simple JSON string
U8 *JSONBuildObject(U8 *key1, U8 *val1, U8 *key2, U8 *val2) {
  return StrFormat("{\"" + key1 + "\":\"" + val1 + "\",\"" + key2 + "\":\"" + val2 + "\"}");
}

// Escape JSON string
U8 *JSONEscape(U8 *str) {
  I64 len = StrLen(str);
  U8 *result = MAlloc(len * 2 + 1);
  I64 j = 0;
  
  for (I64 i = 0; i < len; i++) {
    U8 c = str[i];
    
    if (c == '"') {
      result[j++] = '\\';
      result[j++] = '"';
    } else if (c == '\\') {
      result[j++] = '\\';
      result[j++] = '\\';
    } else if (c == '\n') {
      result[j++] = '\\';
      result[j++] = 'n';
    } else if (c == '\r') {
      result[j++] = '\\';
      result[j++] = 'r';
    } else if (c == '\t') {
      result[j++] = '\\';
      result[j++] = 't';
    } else {
      result[j++] = c;
    }
  }
  
  result[j] = 0;
  return result;
}

// Pretty print JSON (add newlines and indentation)
U8 *JSONPrettyPrint(U8 *json) {
  I64 len = StrLen(json);
  U8 *result = MAlloc(len * 3 + 1);
  I64 j = 0;
  I64 indent = 0;
  Bool in_string = FALSE;
  
  for (I64 i = 0; i < len; i++) {
    U8 c = json[i];
    
    if (c == '"' && json[i-1] != '\\') {
      in_string = !in_string;
    }
    
    if (!in_string) {
      if (c == '{' || c == '[') {
        result[j++] = c;
        result[j++] = '\n';
        indent++;
        for (I64 k = 0; k < indent * 2; k++) result[j++] = ' ';
      } else if (c == '}' || c == ']') {
        result[j++] = '\n';
        indent--;
        for (I64 k = 0; k < indent * 2; k++) result[j++] = ' ';
        result[j++] = c;
      } else if (c == ',') {
        result[j++] = c;
        result[j++] = '\n';
        for (I64 k = 0; k < indent * 2; k++) result[j++] = ' ';
      } else if (c == ':') {
        result[j++] = c;
        result[j++] = ' ';
      } else if (c != ' ' && c != '\t' && c != '\n' && c != '\r') {
        result[j++] = c;
      }
    } else {
      result[j++] = c;
    }
  }
  
  result[j] = 0;
  return result;
}
