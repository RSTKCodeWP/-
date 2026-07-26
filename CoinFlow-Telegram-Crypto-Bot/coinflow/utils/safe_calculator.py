"""Safe calculator without eval() for security."""

import ast
import operator
from typing import Optional


class SafeCalculator:
    """Safe calculator that doesn't use eval()."""
    
    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.FloorDiv: operator.floordiv,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }
    
    def evaluate(self, expression: str) -> Optional[float]:
        """
        Safely evaluate a mathematical expression.
        
        Args:
            expression: Mathematical expression as string
        
        Returns:
            Result of evaluation or None if invalid
        """
        try:
            # Remove whitespace
            expression = expression.strip()
            
            # Parse the expression into an AST
            tree = ast.parse(expression, mode='eval')
            
            # Evaluate the AST
            result = self._eval_node(tree.body)
            
            return float(result)
        except (SyntaxError, ValueError, TypeError, KeyError, ZeroDivisionError):
            return None
    
    def _eval_node(self, node):
        """
        Recursively evaluate AST node.
        
        Args:
            node: AST node to evaluate
        
        Returns:
            Evaluation result
        """
        if isinstance(node, ast.Num):
            # Number literal
            return node.n
        elif isinstance(node, ast.Constant):
            # Constant (Python 3.8+)
            return node.value
        elif isinstance(node, ast.BinOp):
            # Binary operation (e.g., +, -, *, /)
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op = self.OPERATORS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op)}")
            return op(left, right)
        elif isinstance(node, ast.UnaryOp):
            # Unary operation (e.g., -x, +x)
            operand = self._eval_node(node.operand)
            op = self.OPERATORS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op)}")
            return op(operand)
        else:
            raise ValueError(f"Unsupported node type: {type(node)}")
    
    def format_result(self, result: Optional[float]) -> str:
        """
        Format calculation result.
        
        Args:
            result: Calculation result
        
        Returns:
            Formatted string
        """
        if result is None:
            return "Invalid expression"
        
        # Format with appropriate precision
        if abs(result) < 0.01 or abs(result) > 1000000:
            return f"{result:.6e}"
        elif abs(result - int(result)) < 1e-10:
            return str(int(result))
        else:
            return f"{result:.6f}".rstrip('0').rstrip('.')
