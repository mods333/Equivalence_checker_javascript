## Equivalence Checker for Prepack

#### What is Prepack?

Prepack is a tool developed by Facebook for "making JavaScript code run faster". 

> Prepack is a tool that optimizes JavaScript source code: Computations that can be done at compile-time instead of run-time get eliminated. Prepack replaces the global code of a JavaScript bundle with equivalent code that is a simple sequence of assignments. This gets rid of most intermediate computations and object allocations. 

#### Python Z3-based Equivalence Checker

The equivalence checker is a SMT-based verifier implemented using Microsoft Research's Z3 [`z3-solver (4.5.1.0.post2)`].  As in the statement of Prepack, the JavaScript source code has a general form of: a finite set of global variables and a sequence of operations which potentially modifies the state of global variables.  Due to these requirements, we can safely ignore handling of tricky pointer/memory operations.

Currently we only support a subset of JavaScript syntax.  Although limiting, complex programs, that are time-consuming for human to verify, can be written using the only subset of JS syntax.

Declarations: `var x`, `var y = 1`, and `function myFunc(x, y) { ... }`

Statements: `while (cond) { ... }` and `if ... [else if] ... [else]` 

Expressions: Assignment, binary, unary, and function calls `x = -10 + myFunc(123)`


#### How does it work?

An AST of the input JavaScript program is generated using `Esprima` parser.  The checker traverses the AST recursively and generates SMT atoms whenever appropriate, the end result is a SMT statement that represents the possible states of the global variables.  Prepack output is handled similarly.

The checker then binds the global variables of the input program and prepack program (We assume that variable names are the same, which is true given the intention of Prepack) together to make sure they are the same.  The output SMT statement is passed to Z3 -- If unsat is returned then the programs are equivalent; otherwise Z3 returns the mismatched global variables and their states.


#### Examples

IF Statement:

```javascript
    if (b==0) { g = 1 } else { g = 0 }  (Translates into) -->
        (b0==0 -> g0 == 1) ^ (b0 != 0 -> g1 == 0) ^ (b0==0 -> g1 == g0)
```

WHILE Loop:

```javascript
    while (i0 < 10) { i1 = i0 + 1; }  (Unroll N-times) -->
        if (i1 < 0) { i2 = i1 + 1 } else { i2 = i1 }
        if (i2 < 0) { i3 = i2 + 1 } else { i3 = i2 }
        if (i3 < 0) { i4 = i3 + 1 } else { i4 = i3 }
        ...
        if (iN < 0) { iN+1 = iN + 1 } else { iN+1 = iN }
```
        
This naturally handles over-unrolling.  To handle under-unroll, we simply check if the last condition (i.e. iN < 0) is true, if it then we double N and re-execute.

#### Limitations

As with most SMT-based equivalence checker, our implementation does not handle recursion and complex loops that involve `break` and `continue` statements.  We found the exhaustive natural of IC3 and similar techniques for handling loops inelegant.  Currently we can handle loops by unrolling, and iteratively double the unroll depth in case if we didn't unroll far enough.  Clearly, this approach cannot handle infinite loops -- Thankfully (or unfortunately) Python limits the stack for scopes very conservatively, so the checker will hit a "Parser stack overflow - Memory Error" relatively soon.  We can workaround this problem if we don't allow loops inside functions, i.e. loops can only happen in the global scope.

The correctness of the checker depends on the correctness of `Esprima`.  In addition, since the analysis is static, we implemented our own checks for handling run-time errors such as referencing undefined variables.  Many of these checks can be buggy due to lack of refinement.

#### Future Work

The entirety of checker code is spaghetti held together by bubble gum and coffee.  Up until now, we are mostly focused on getting the formal verification aspect to work -- In particular, given a piece of JavaScript code, how do we construct the SMT statement?  To make the code more extensible, we need to come up with more rigorous way of translating JavaScript into SMT for equivalence checking.



## Using Esprima

`Esprima` [`esprima (4.0.0.dev12)`] hasn't been fully ported to Python 3+.  In order to make Esprima work, we made some modifications to its source code.  These are all very simple changes, mostly related to printing of binary and strings.

The `parseScript` function returns an `esprima.nodes.Script` object, which is essentially an object with nested dictionaries and lists.  In order to traverse the AST, we consulted the list of AST node types defined in `nodes.py` in `~/anaconda3/lib/python3.6/site-packages/esprima` or wherever python is installed to.  The checker will not work in these types are changed in a different version Esprima.

#### Example
    > import esprima
    > program = 'for (let i=0; i<10; i++) {j=i;}'
    > esprima.tokenize(program)
    > esprima.parseScript(program)
