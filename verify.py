import copy
import esprima
import esprima.nodes as nodes
import re
import subprocess
from z3 import *

def printWithIndent(text, level):
    print('  ' * level, end='')
    print(text)

def representsInt(s):
    try: 
        int(s)
        return True
    except ValueError:
        return False

def fn_lookup(var, varTable, funcTable, level, flag = 0, funcScope = ''):
    if (level == -1):
       print ("Error in variable name lookup")
       exit(-1)

    # print('------------------')
    # print('in lookup')
    # print('{} {} {}'.format(var, level, funcScope))
    # print('var {}'.format(varTable))
    # print('func {}'.format(funcTable))
    # print('------------------')

    if funcScope == '':
        # Should look inside varTable
        if level in varTable and var in varTable[level]:
            if flag == 1:
                varTable[level][var] += 1
            return level, varTable[level][var]
        else:
            return fn_lookup(var, varTable, funcTable, level-1, flag, funcScope)
    else:
        # Inside a function, look  at funcTable
        if level-1 in funcTable and funcScope in funcTable[level-1] and var in funcTable[level-1][funcScope]['varTable']:
            if flag == 1:
                funcTable[level-1][funcScope]['varTable'][var] += 1
            return level, funcTable[level-1][funcScope]['varTable'][var]
        else:
            return fn_lookup(var, varTable, funcTable, level-1, flag, funcScope)

def funcTable_lookup(funcName, level, funcTable):
    if (level == -1):
        print ("Error in funcTable lookup")
        exit(-1)

    if level in funcTable and funcName in funcTable[level]:
        return level, funcTable[level][funcName]
    else:
        return funcTable_lookup(funcName, level-1, funcTable)

class Counter:
    cnt = 0

def printCondPython(ast, varTable, level, funcScope, funcTable):
    if isinstance(ast, nodes.BinaryExpression):
        # LogicalExpression is just BinaryExpression
        if ast.type == 'LogicalExpression':
            leftStr = printCondPython(ast.left, varTable, level, funcScope, funcTable)
            rightStr = printCondPython(ast.right, varTable, level, funcScope, funcTable)
            
            if ast.operator == '&&':
                tempStr = '({} and {})'
                return tempStr.format(leftStr, rightStr)
            elif ast.operator == '||':
                tempStr = '({} or {})'
                return tempStr.format(leftStr, rightStr)
            else:
                # FIXME: What can this operator be?
                tempStr = '({}{}{})'.format(leftStr, ast.operator, rightStr)
                return tempStr
        else:
            # Left association, go down leftside first
            leftStr = printCondPython(ast.left, varTable, level, funcScope, funcTable)
            rightStr = printCondPython(ast.right, varTable, level, funcScope, funcTable)
            tempstr = '(' + leftStr + ast.operator + rightStr + ')'
            return tempstr

    elif isinstance(ast, nodes.UnaryExpression):
        """
        UnaryExpression
            prefix: boolean
            operator: str
            argument: dict
        """

        argStr = printCondPython(ast.argument, varTable, level, funcScope, funcTable)
        # FIXME: what's prefix?
        if ast.operator == '!':
            retStr = '(not {})'.format(argStr)
        elif ast.operator == '-':
            retStr = ast.operator + argStr
        else:
            # FIXME: what else is here?
            exit('Unhandled operator in UnaryExpression')

        return retStr

    elif isinstance(ast, nodes.Identifier):
        lookupName = funcScope + ast.name
        levelFound, index = fn_lookup(lookupName, varTable, funcTable, level, funcScope=funcScope)
        if funcScope == '':
            retStr = '{}{}_{}'.format(lookupName, levelFound, index)
        else:
            retStr = '{}{}_{}_{{nInvoke}}'.format(lookupName, levelFound, index)
        
        return retStr

    elif isinstance(ast, nodes.Literal):
        return ast.raw
    else:
        print ('Uh-oh. Unhandle type {} in printCondPython'.format(ast.type))
        exit(-1)

def printSMT(ast, varTable, level, funcScope = '', funcTable = None, additionalSMT = None, incFlag = 0, whileCount = None, loopUnroll=5):
    
    if DEBUG_MODE:
        # print('----------------')printWithIndent
        printWithIndent('level {}, type: {}'.format(level, ast.type), level)
        # print('----------------')
        # printWithIndent('varTable: {}'.format(varTable), level + 1)
        # print('----------------')
        # printWithIndent('funcTable: {}'.format(funcTable), level + 1)
        # print('----------------')
        # print()
    
    if funcTable == None:
        funcTable = {}

    if additionalSMT == None:
        additionalSMT = []

    if whileCount == None:
        whileCount = []

    if isinstance(ast, nodes.Script):
        # Assuming ast.body is always a list..?
        # just need to recurse into each element of body
        tempStr = ''
        for element in ast.body:
            outStr = printSMT(element, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)
            tempStr = outStr if tempStr == '' else tempStr + '^' + outStr
        
        for smt in additionalSMT:
            tempStr = tempStr + '^' + smt

        # print('----------------')
        # print('varTable {}'.format(varTable))
        # print('----------------')
        # print('funcTable {}'.format(funcTable))
        # print('----------------')

        return tempStr, whileCount

    elif isinstance(ast, nodes.VariableDeclaration):
        """
        VariableDeclaration:
            declarations: list
            kind: ex. 'var'
        """

        if funcScope == '':
            if level in varTable:
                localVars = varTable[level]
            else:
                localVars = {}
                varTable[level] = localVars
        else:
            localVars = funcTable[level-1][funcScope]['varTable']

        retStr = ''
        for decl in ast.declarations:

            lookupName = funcScope + decl.id.name
            # For declaration just init to 0
            localVars[lookupName] = 0

            # # Construct SMT expression
            # tempStr = '({}=={})'.format(lookupName + str(level) + '_' + str(0), lookupName + str(level))

            if decl.init:
                # RHS can be any expression... like func calls, binary expr, etc
                # Must do init before left, because left increments counter
                initStr = printSMT(decl.init, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)
                leftStr = printSMT(decl.id, varTable, level, funcScope, funcTable, additionalSMT, 1, whileCount, loopUnroll)
                tempStr = '({}=={})'.format(leftStr, initStr)
            else:
                leftStr = printSMT(decl.id, varTable, level, funcScope, funcTable, additionalSMT, 1, whileCount, loopUnroll)
                tempStr = '({}=={})'.format(leftStr, leftStr)
            
            if retStr == '':
                retStr = tempStr
            else:
                retStr = retStr + '^' + tempStr
        
        # varTable[level] = localVars
        return retStr
    elif isinstance(ast, nodes.ExpressionStatement):
        """
        ExpressionStatement:
            expression: dict
        """
        
        # Can we assume there's only one ExpressionStatement here?
        return printSMT(ast.expression, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)

    elif isinstance(ast, nodes.CallExpression):
        """
        CallExpression
            callee: dict
        """
        
        if isinstance(ast.callee, nodes.Identifier):
            # If callee is an indentifier, this is just a normal function call inside main program
            # ex. y = add2(3)
            calledFunc = ast.callee.name
            
            foundLevel, localTable = funcTable_lookup(calledFunc, level, funcTable)

            SMTExpr = localTable['SMTExpr']
            params = localTable['params']
            nInvoke = localTable['nInvoke']

            localTable['nInvoke'] += 1
            # Replace variables with correct nInvoke
            SMTExpr = SMTExpr.replace('{nInvoke}', str(nInvoke))

            if len(params) != len(ast.arguments):
                print ('Uh-oh, something went wrong!')
                exit(-1)

            # Replace input parameter with correct values
            for index, arg in enumerate(ast.arguments):
                tempStr = printSMT(arg, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)
                SMTExpr = SMTExpr.replace('{'+params[index]+'}', tempStr)

            # No need to recursive 
            # FIXME: How to add SMTExpr?
            additionalSMT.append(SMTExpr)
            retVar = 'ret{}_{}'.format(calledFunc, nInvoke)
            return retVar
        else:
            # FIXME: is this right?
            return printSMT(ast.callee, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)

    elif isinstance(ast, nodes.AssignmentExpression):
        """
        AssignmentExpression
            left: dict
            right: dict
        """

        # Must do right before left
        rightStr = printSMT(ast.right, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)
        leftStr = printSMT(ast.left, varTable, level, funcScope, funcTable, additionalSMT, 1, whileCount, loopUnroll)
        
        return '({}=={})'.format(leftStr, rightStr)

    elif isinstance(ast, nodes.BlockStatement):
        """
        BlockStatement
            body: list
        """

        level = level + 1
        tempstr = ''
        for stmt in ast.body:
            outStr = printSMT(stmt, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)
            tempstr = outStr if tempstr == '' else '(And({},{}))'.format(tempstr, outStr)

        return tempstr

    elif isinstance(ast, nodes.FunctionExpression):
        """
        FunctionExpression:
            self.expression = False
            self.async = False
            self.id = id (function name)
            self.params = list
            self.body = dict
            self.generator = generator (always false?)
        """
        
        # FIXME: need to handle parameters
        return printSMT(ast.body, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)

    elif isinstance(ast, nodes.FunctionDeclaration):
        """
        FunctionDeclaration
            id: dict
            params: list
            body: dict
        """

        # FIXME: FunctionDeclaration should be considered as the beginning of a new scope
        # 1. Need to add vars in parameter list to varTable[level + 1]
        if (level+1) not in varTable:
            varTable[level+1] = {}
        
        funcName = ast.id.name

        # Function needs to maintain an invocation history,
        # Every invocation need to use a different set of variable names
        if level not in funcTable:
            funcTable[level] = {}
        
        if funcName not in funcTable[level]:
            funcTable[level][funcName] = {}
        
        localTable = funcTable[level][funcName]

        localTable['varTable'] = {}
        for param in ast.params:
            localTable['varTable'][funcName + param.name] = 0

        localTable['nInvoke'] = 0

        localTable['params'] = [funcName + param.name for param in ast.params]

        bindInputStr = ''
        for index, param in enumerate(ast.params):
            lookupName = funcName + param.name
            tempStr = '({{{}}}=={}{}_{}_{{nInvoke}})'.format(lookupName, lookupName, level+1, 0)
            bindInputStr = tempStr if bindInputStr == '' else bindInputStr + '^' + tempStr

        tempStr = printSMT(ast.body, varTable, level, funcName, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)
        if bindInputStr == '':
            localTable['SMTExpr'] = tempStr
        else:
            localTable['SMTExpr'] = '{}^{}'.format(bindInputStr, tempStr)

        # FunctionDeclaration doesn't need to return anything, return true..
        return '(1==1)'

    elif isinstance(ast, nodes.ReturnStatement):
        """
        ReturnStatement
            argument: dict
        """
        tempStr = printSMT(ast.argument, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)
        retStr = '(ret{}_{{nInvoke}}=={})'.format(funcScope, tempStr)
        return retStr

    elif isinstance(ast, nodes.BinaryExpression):
        """
        Binary Expression
            operator: str
            left: dict
            right: dict
        """

        # LogicalExpression is just BinaryExpression
        if ast.type == 'LogicalExpression':
            leftStr = printSMT(ast.left, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)
            rightStr = printSMT(ast.right, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)
            
            if ast.operator == '&&':
                tempStr = 'And({}, {})'
                return tempStr.format(leftStr, rightStr)
            elif ast.operator == '||':
                tempStr = 'Or({}, {})'
                return tempStr.format(leftStr, rightStr)
            else:
                # FIXME: What can this operator be?
                tempStr = '({}{}{})'.format(leftStr, ast.operator, rightStr)
                return tempStr
        else:
            # Left association, go down leftside first
            leftStr = printSMT(ast.left, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)
            rightStr = printSMT(ast.right, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)
            tempstr = '(' + leftStr + ast.operator + rightStr + ')'
            return tempstr

    elif isinstance(ast, nodes.UnaryExpression):
        """
        UnaryExpression
            prefix: boolean
            operator: str
            argument: dict
        """

        argStr = printSMT(ast.argument, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)
        # FIXME: what's prefix?
        if ast.operator == '!':
            retStr = 'Not({})'.format(argStr)
        elif ast.operator == '-':
            retStr = ast.operator + argStr
        else:
            # FIXME: what else is here?
            exit('Unhandled operator in UnaryExpression')

        return retStr

    elif isinstance(ast, nodes.IfStatement):
        """
        IfStatement
            test: dict
            consequent: dict
            alternate: dict
        """

        # if (b==0) { g = 1 } else { g = 0 }
        #    (b0==0 -> g0 == 1) ^ (b0 != 0 -> g1 == 0) ^ (b0==0 -> g1 == g0)

        # Handle condition, should be a simple expression
        condStr = printSMT(ast.test, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)
        conseqStr = printSMT(ast.consequent, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)
        retStr = '(Implies({}, {}))'.format(condStr, conseqStr)

        if (ast.alternate == None):
            return retStr
        else:
            # Also need to handle the alt. case 

            # Need to save a copy of the varTable
            # print (varTable)
            # print ('{} {}'.format(funcScope, level))
            localTable = varTable if funcScope == '' else funcTable     
            localTableCopy = copy.deepcopy(localTable)

            altStr = printSMT(ast.alternate, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)
            
            # Need to get the counters for variables that have changed.. 
            connectStr = ''
            for level in localTable.keys():
                for varName in localTable[level].keys():
                    oldCount = localTableCopy[level][varName]
                    newCount = localTable[level][varName]
                    if oldCount != newCount:
                        oldVarName = '{}{}_{}'.format(varName, level, oldCount)
                        newVarName = '{}{}_{}'.format(varName, level, newCount)
                        tempStr = '({}=={})'.format(newVarName, oldVarName)
                        connectStr = tempStr if connectStr == '' else connectStr + '^' + tempStr

            tempStr1 = '(Implies(Not({}),{}))'.format(condStr, altStr)

            if connectStr == '':
                # Nothing changed 
                retStr = '(And({},{}))'.format(retStr, tempStr1)
            else:
                # Nothing changed, need to bind
                tempStr2 = '(Implies({},({})))'.format(condStr, connectStr)
                retStr = '(And(And({},{}),{}))'.format(retStr, tempStr1, tempStr2)
            
            return retStr

    elif isinstance(ast, nodes.WhileStatement):
        """
        WhileStatement
            test: dict
            body: dict
        """

        retStr = ''
        for i in range(LOOP_UNROLL_DEPTH):

            # Save table
            localTable = varTable if funcScope == '' else funcTable     
            localTableCopy = copy.deepcopy(localTable)

            condStr = printSMT(ast.test, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)
            bodyStr = printSMT(ast.body, varTable, level, funcScope, funcTable, additionalSMT, incFlag, whileCount, loopUnroll)

            # Just do the same thing as IfStatement...
            # FIXME: Need to add finished_loop_N
            bodyStr = '(1==1)' if bodyStr == '' else bodyStr
            thenStr = '(Implies({},{}))'.format(condStr, bodyStr)

            connectStr = ''
            for level in localTable.keys():
                for varName in localTable[level].keys():
                    oldCount = localTableCopy[level][varName]
                    newCount = localTable[level][varName]
                    if oldCount != newCount:
                        oldVarName = '{}{}_{}'.format(varName, level, oldCount)
                        newVarName = '{}{}_{}'.format(varName, level, newCount)
                        tempStr = '({}=={})'.format(newVarName, oldVarName)
                        connectStr = tempStr if connectStr == '' else '(And({},{}))'.format(connectStr, tempStr)
            
            # If condition not true, we need to maintain variable state
            connectStr = '(1==1)' if connectStr == '' else connectStr
            maintainStr = '(Implies(Not({}),{}))'.format(condStr, connectStr)

            combinedStr = '(And({},{}))'.format(thenStr, maintainStr)
            retStr = combinedStr if retStr == '' else '(And({},{}))'.format(retStr, combinedStr)

            if i == range(LOOP_UNROLL_DEPTH)[LOOP_UNROLL_DEPTH-1]:
                pyCondStr = printCondPython(ast.test, varTable, level, funcScope, funcTable)
                whileCount.append(pyCondStr)

            additionalSMT.append(combinedStr)

        return '(1==1)'

    elif isinstance(ast, nodes.Identifier):
        lookupName = funcScope + ast.name
        levelFound, index = fn_lookup(lookupName, varTable, funcTable, level, flag=incFlag, funcScope=funcScope)
        if funcScope == '':
            retStr = '{}{}_{}'.format(lookupName, levelFound, index)
        else:
            retStr = '{}{}_{}_{{nInvoke}}'.format(lookupName, levelFound, index)
        
        return retStr

    elif isinstance(ast, nodes.Literal):
        return ast.raw
    else:
        return ''

def writeSMTCheckScript(fileHandle):
    text = """
def representsInt(s):
    try: 
        int(s)
        return True
    except ValueError:
        return False

if DEBUG_MODE:
    print ('SMT Expression: ')
    print (s.sexpr())

if s.check() == sat:
    # print ('sat')
    smtModel = s.model()
    if DEBUG_MODE:
        print (smtModel)

    smtModelDict = {}
    for index, item in enumerate(smtModel):
        smtModelDict[str(item)] = smtModel[item].as_long()

    for _, varTuple in enumerate(connectingVars):
        var, ppVar = varTuple[0], varTuple[1]
        varVal, ppVarVal = smtModelDict[var], smtModelDict[ppVar]
        if varVal != ppVarVal:
            print ('{}={} vs. {}={}'.format(var, varVal, ppVar, ppVarVal))

    # Check for under-unrolled
    for item in whileChecks:
        for smtVarName in [ x.strip() for x in re.split(OPERATOR_STR, item) if x.strip() != '']:
            if not representsInt(smtVarName) and smtVarName not in ['and', 'or', 'not']:
                item = item.replace(smtVarName, str(smtModelDict[smtVarName]))
        # If item is True, then we didn't unroll enough
        # return True so we can rerun
        if eval(item):
            # returncode 2 for need more unroll
            exit(2)
    
    # returncode 1 for sat
    exit(1)
    
else:
    # returncode 0 for unsat
    # print ('unsat')
    exit(0)
    """
    fileHandle.write(text + '\n')

def main(program, loopUnroll=5, insertFake=True, fileName=None):
    OPERATOR_STR = '==|\+|-|\*|/|\(|\)|And|Implies|Or|Not|,|>|>=|<|<=|!='
    
    fileHandle = open(fileName, 'w')
    fileHandle.write('import re\n')
    fileHandle.write('from z3 import *\n')
    fileHandle.write('DEBUG_MODE = {}\n'.format(DEBUG_MODE))
    fileHandle.write('OPERATOR_STR = "{}"\n'.format(OPERATOR_STR))
    fileHandle.write('s = Solver()\n')

    variableLookup = {}
    # print(esprima.tokenize(program))
    parsedTree = esprima.parseScript(program)
    if DEBUG_MODE:
        print (parsedTree)

    print ('Parsing original program')
    SMTExpr, whileChecks = printSMT(parsedTree, varTable=variableLookup, level=0, loopUnroll=loopUnroll)
    if DEBUG_MODE:
        # print (variableLookup)
        print (SMTExpr)
        print ()

    # Execute prepack
    prepackLookup = {}
    prepackProgramByte = subprocess.check_output(['prepack', programFile])

    prepackProgram = ''
    checkSeenVar = {}
    for line in prepackProgramByte.decode().strip().split('\n'):
        # FIXME: Assume prepack only outputs assignment statements...
        varName = line.split('=')
        varName = varName[0].strip()
        if varName not in checkSeenVar:
            prepackProgram = prepackProgram + 'var pp' + varName + ';\n'
            checkSeenVar[varName] = True
        prepackProgram = prepackProgram + 'pp' + line + '\n'

    if insertFake:
        prepackProgram += 'ppy = 100;\n'

    prepackTree = esprima.parseScript(prepackProgram)
    print ('Parsing prepack output')
    prepackSMT, _ = printSMT(prepackTree, varTable=prepackLookup, level=0)
    if DEBUG_MODE:
        print (prepackSMT)
        print ()

    # SMT?
    # Generate original variables (directly from SMTExpr)
    seenVar = {}
    for clause in SMTExpr.split('^'):
        # ex. ['(ajasd==asd)', '(quiwe==zxc)', (AND(x1, x2) )]
        # tempStr = clause.replace('(', '').replace(')', '')
        tempStr = re.sub('\s', '', clause)
        # FIXME: Need to consider other operators as well
        for smtVarName in [ x for x in re.split(OPERATOR_STR, tempStr) if x != '']:
            if smtVarName not in seenVar and not representsInt(smtVarName):
                seenVar[smtVarName] = True
                # print("{} = BitVec('{}', 32)".format(smtVarName, smtVarName))
                fileHandle.write("{} = BitVec('{}', 32)\n".format(smtVarName, smtVarName))
                # exec("{} = BitVec('{}', 32)".format(smtVarName, smtVarName))

    # Generate prepack variables
    for clause in prepackSMT.split('^'):
        # ex. ['(ajasd==asd)', '(quiwe==zxc)']
        # tempStr = clause.replace('(', '').replace(')', '')
        tempStr = re.sub('\s', '', clause)
        # FIXME: Need to consider other operators as well
        for smtVarName in [ x for x in re.split(OPERATOR_STR, tempStr) if x != '']:
            if smtVarName not in seenVar and not representsInt(smtVarName):
                seenVar[smtVarName] = True
                # print("{} = BitVec('{}', 32)".format(smtVarName, smtVarName))
                fileHandle.write("{} = BitVec('{}', 32)\n".format(smtVarName, smtVarName))
                # exec("{} = BitVec('{}', 32)".format(smtVarName, smtVarName))

    # solver = Solver()
    # Generate the add clauses for original program
    for clause in SMTExpr.split('^'):
        # print('s.add({})'.format(clause))
        fileHandle.write('s.add({})\n'.format(clause))
        # solver.add(eval(clause))

    # Generate the add clauses for prepack program
    for clause in prepackSMT.split('^'):
        #print('s.add({})'.format(clause))
        fileHandle.write('s.add({})\n'.format(clause))
        # solver.add(eval(clause))

    # We are assuming the global variables are defined at level 0
    # And only the state of global variables matters
    concatStr = 'And('
    connectingVars = []
    for varName in variableLookup[0].keys():
        # We prepended prepack variables with pp...
        prepackIndex = prepackLookup[0]['pp' + varName]
        programIndex = variableLookup[0][varName]
        programVarName = '{}{}_{}'.format(varName, 0, programIndex)
        prepackVarName = 'pp{}{}_{}'.format(varName, 0, prepackIndex)
        compareClause = '({}=={})'.format(programVarName, prepackVarName)
        concatStr = concatStr + compareClause + ','
        connectingVars.append((programVarName, prepackVarName))

    concatStr = 'Not(' + concatStr[:-1] + '))'
    # print (concatStr)
    fileHandle.write('s.add({})\n'.format(concatStr))
    # solver.add(eval(concatStr))

    # if DEBUG_MODE:
    #     print ('SMT Expression: ')
    #     print (solver.sexpr())

    print ('SMT Result: ')

    fileHandle.write('connectingVars = {}\n'.format(connectingVars))
    fileHandle.write('whileChecks = {}\n'.format(whileChecks))
    writeSMTCheckScript(fileHandle)
    fileHandle.flush()
    smtResult = subprocess.run(['python', fileName])
    
    if smtResult.returncode == 1:
        print ('sat')
    elif smtResult.returncode == 2:
        print ('sat, but need to unroll more')
        fileHandle.close()
        return True
    else:
        print ('unsat')


if __name__ == '__main__':

    INSERT_FAKE_CODE = False
    LOOP_UNROLL_DEPTH = 2
    DEBUG_MODE = False
    programFile = 'simple_script.js'

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", help="insert fake code for debugging",
                    action="store_true")
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                    action="store_true")
    parser.add_argument("-f", "--file", help="input JavaScript file (default simple_script.js)")
    args = parser.parse_args()


    if args.verbose:
        DEBUG_MODE = True
    
    if args.debug:
        INSERT_FAKE_CODE = True

    if args.file:
        programFile = args.file

    try:
        with open(programFile) as f:
            program = f.read()
    except FileNotFoundError as e:
        print (e)
        exit(-1)


    tempFile = 'pyz3_output.py'
    redo = main(program=program, loopUnroll=LOOP_UNROLL_DEPTH, insertFake=INSERT_FAKE_CODE, fileName=tempFile)

    while redo:
        LOOP_UNROLL_DEPTH = LOOP_UNROLL_DEPTH * 2
        print ()
        print ('Increasing Loop Unroll Depth to {}'.format(LOOP_UNROLL_DEPTH))
        redo = main(program=program, loopUnroll=LOOP_UNROLL_DEPTH, insertFake=INSERT_FAKE_CODE, fileName=tempFile)
