# Connections & Data Flow

## How Connections Work

Data flows **left to right** through the graph. Each connection carries a value from an output port to an input port. During each update cycle, the compiler evaluates nodes in topological order (upstream before downstream).

### Making Connections

1. Hover over an **output port** (right side of a node)
2. Click and drag to an **input port** (left side of another node)
3. Release to create the connection

### Removing Connections

- Click on a connection line to select it, then press **Delete** or **Backspace**

## Port Types

Ports are color-coded by their data type:

| Type | Color | Values |
| --- | --- | --- |
| Number | Blue | Integers or floats (`0`, `3.14`, `-100`) |
| Boolean | Purple | `true` or `false` |
| String | Yellow/Amber | Text values (`"Hello"`) |
| Any | Gray | Accepts any type |

## Type Compatibility

- **Exact match** - Number-to-Number, Boolean-to-Boolean always works
- **Any port** - An `any` port accepts connections from any type
- **Number to Boolean** - A number output can connect to a boolean input (`0` = false, non-zero = true)
- **Boolean to Number** - A boolean output can connect to a number input (`true` = 1, `false` = 0)
- **Incompatible** - String ports cannot connect to Number/Boolean ports (the editor prevents this)

## Rules

- Each **input port** accepts only **one** connection (last one wins if you drag a second)
- Each **output port** can connect to **multiple** inputs (fan-out)
- **Cycles** are not allowed - the compiler detects them and reports an error
- Unconnected input ports use their **default value** (shown in the inspector)

## Data Flow Example

```
Battery(Voltage) --> Compare(A)
                                  --> Compare(Result) --> GCS Text(Trigger)
Constant(11.1)   --> Compare(B)
```

Each cycle: Battery reads voltage, Constant provides 11.1, Compare checks if voltage < 11.1, and the result triggers (or not) the GCS Text message.
