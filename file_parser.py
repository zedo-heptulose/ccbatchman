import re
import itertools as itt
import logging as log

#READ DATA FROM ONE FILE

float_pattern = r'(-?\d+\.\d+)'
int_pattern = r'(-?[0-9]+)'
log.basicConfig(level=log.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_match_at_index(matches, index):
    '''this is chatgpt code'''
    # Consume matches until reaching the desired index
    for _ in range(index + 1):
        try:
            match = next(matches)
        except StopIteration:
            return None  # Return None if index is out of range
    return match

def read_var_from_line(line,var_type,var_flag= None,var_regex=None):
	'''
	function that handles variable as proper type
 	'''
	log.debug("in read_var_from_line:")
	log.debug(line)
	log.debug(var_regex)
 
	if var_regex == None:
		if var_type == "float":
			var_regex = float_pattern
		if var_type == "integer":
			var_regex = int_pattern
		if var_type == "string":
			raise ValueError("string type specified without regular expression")
      
	matches = re.finditer(var_regex,line)
	if not matches:
		raise ValueError("variable regex did not match line\n")


	if var_flag == None:
		match = next(matches)
	elif var_flag == 'last':
		log.debug('flag last reached')
		for matcher in matches:
			match = matcher
	elif re.search(int_pattern,var_flag):
		index = int(re.match(int_pattern,var_flag).group(0))
		match = get_match_at_index(matches, index)
  

	variable = match.group(1)

	if var_type == "float":
		return float(variable)
	if var_type == "integer":
		return int(variable)
	if var_type == "string":
		return str(variable)


			


	
def hidden_operation(line, sr_flag=None, last_value=None, var_type=None, var_flag=None, var_regex=None):
	'''
	the internal function called by procedure(line) which is returned by file_make_test_and_procedure
	'''
	if sr_flag is None:
		raise ValueError('operation used with only line variable\n')
	log.debug('in hidden operation')
	log.debug(line.strip())
	log.debug(sr_flag)
 
	if re.search("first", sr_flag):
		log.debug('in first')
		if last_value is None:
			log.debug('returning read_var_from_line with var_regex and var_type')
			return read_var_from_line(line, var_type, var_flag, var_regex)
		else:
			log.debug('returning last_value')
			return last_value
	if re.search("last", sr_flag):
		#log.debug('returning read_var_from_line with var_regex and var_type')
		return read_var_from_line(line, var_type, var_flag, var_regex)
	if re.search("largest", sr_flag):
     
		log.debug('in largest')
		temp = read_var_from_line(line, var_type, var_flag, var_regex)
		if last_value is None:
			log.debug('returning temp')
			return temp
		if temp > last_value:
			log.debug('returning temp')
			return temp
		if temp <= last_value:
			log.debug('returning last_value')
			return last_value
	if re.search("smallest", sr_flag):
     
		log.debug('in smallest')
		temp = read_var_from_line(line, var_type, var_flag, var_regex)
		if last_value is None:
			log.debug('returning temp')
			return temp
		if temp > last_value:
			log.debug('returning last_value')
			return last_value
		if temp <= last_value:
			log.debug('returning temp')
			return temp

	if re.search("sum_all", sr_flag):
		log.debug('in sum_all')
		temp = read_var_from_line(line, var_type, var_flag, var_regex)
		if last_value is None:
			log.debug('returning temp')
			return temp
		log.debug('returning temp + last_value')
		return temp + last_value

	if re.search("found", sr_flag):
		log.debug('in found, returning True')
		return True

	if re.search("not_found", sr_flag):
		log.debug('in not_found, returning False')
		return False

	if re.search("at_least_2", sr_flag):
		log.debug('in at_least_2')
		if last_value is None:
			log.debug('returning False')
			return False
		if last_value is False:
			log.debug('returning True')
			return True


    
def make_test_and_procedure(search_rule, sr_flag=None, var_type = None, var_flag = None, var_regex = None):
	'''
	makes the two functions based on the rules
	'''
	# log.debug('in make_test_and_procedure')
	# log.debug(search_rule)
	# log.debug(sr_flag)
	# log.debug(var_regex)
	# log.debug(type)
	# log.debug()
	def line_test(line):
		###print('in line_test')
		##print( "|" + search_rule + "|" + '...'+ line)
		if re.search(search_rule, line):
			#log.debug('FOUND!!!')
			return True
		else:
			#log.debug ('FAILED!!')
			return False

	def procedure(line, last_value):
		return hidden_operation(line, sr_flag, last_value, var_type, var_flag, var_regex)

	if sr_flag is None:
		return line_test, None

	return line_test, procedure



def read_rulesfile(rule_filename):
	'''
	function that makes a list of rules from the rulesfile
	'''
	with open(rule_filename, 'r') as rules_file:
		lines = rules_file.readlines()
	
	rule_pattern = r'(?:\s?)([^;]+)(?:;|$)'
	comment_pattern= r'(\s*?#)'
	only_whitespace = r'^\s*$'
	rules_found = []
	for line in lines:
		#search the line for a keyword delimited by a semicolon 
		rule_matches = re.finditer(rule_pattern, line)
		comment_match = re.match(comment_pattern, line)
		blank_match = re.match(only_whitespace, line)
		#check that there are the correct number of matches
		if rule_matches and not comment_match and not blank_match:
			fields = []
			for match in rule_matches:
				fields.append(match.group(1).strip())
			rules_found.append(fields)
   
   #to handle list_of syntax:
	variable_index_dict = dict ()
   
	actions_dict = dict()
	actions_dict['__normal__'] = []
	actions_dict['__after__'] = []
	actions_dict['__before__'] = []
 
	action_dict_key = '__normal__'
	for rule_fields in rules_found:
		##print('rule_fields for varname ' + rule_fields[0] + ':')
		varname = rule_fields[0]
		search_regex = rule_fields[1]
		#check if the rule is a control flow rule first
		if varname == '__after__':
			if len(rule_fields) == 2:
				generated_functions = make_test_and_procedure(search_regex)
    
				line_test = generated_functions[0] #generated functions should give a list,
				#LINE TEST and NONE for __after__ and __before__

				action = (varname, line_test, search_regex)
       
				generated_functions = make_test_and_procedure(search_regex)
				actions_dict['__after__'].append(action)
    
				if actions_dict.get(search_regex) is None:
					actions_dict[search_regex] = []
				action_dict_key = search_regex
			else:
				raise ValueError("need two fields in control flow rule\n")
  
		elif varname == '__before__':
			if len(rule_fields) == 2:				
       
				generated_functions = make_test_and_procedure(search_regex)
				line_test = generated_functions[0]

				action = (varname, line_test, search_regex)
       
				actions_dict['__before__'].append(action)
				action_dict_key = '__normal__'
			else:
				raise ValueError("need exactly two fields in control flow rule\n")

		else:
			if len(rule_fields) < 3:
				##print(rule_fields)
				raise ValueError("^ rule formatted incorrectly\n")
			#if full set of instructions, use all parameters
			search_flag = rule_fields[2]
   
			if len(rule_fields) == 5:
				generated_functions = make_test_and_procedure(search_regex,rule_fields[2],rule_fields[3],rule_fields[4])
			elif len(rule_fields) == 4:
				generated_functions = make_test_and_procedure(search_regex,rule_fields[2],rule_fields[3])
			elif len(rule_fields) == 3:
				generated_functions = make_test_and_procedure(search_regex,rule_fields[2])
			else:
				raise ValueError(str(len(rule_fields)) +" fields found in rule line.\n" )

			line_test = generated_functions[0]
			procedure = generated_functions[1]

			action = (varname, line_test, procedure, search_flag)
			actions_dict[action_dict_key].append(action)

	return actions_dict
















def extract_data(read_filename, ruleset_filename = "data/rules/GAU.rules"):
	'''

	'''
	#some storage data type
	#log.debug ('porque')
	with open(read_filename, 'r') as input:
		lines = input.readlines()
	
	file_data = dict() #dict of varname : returned data
	rules_dict = read_rulesfile(ruleset_filename)
	working_key = '__normal__'
	line_index = 0
	
	##print('starting extract_data')
 	##print(rules_dict)  
	list_var_integers = dict()
 
	for line in lines:
			line_index += 1
			##print(line_index)
   
			##print('using key: ' + working_key)
			#log.debug(len(rules_list))	#consider always checking normal ones and only checking special ones if working key for them used
			for action in rules_dict[working_key]:
				##print('checking working key')
				#log.debug ('gets to action')
				varname = action[0]
				line_test = action[1]
				operation = action[2]
				flag = action[3]
				#list syntax
				#need this to not save the variable format...
				if line_test(line):
					if re.search("list", flag):
						if list_var_integers.get(varname) is None:
							list_var_integers[varname] = 0
						list_var_integers[varname] += 1
						varname = varname.format(str(list_var_integers[varname]))
       
					#print('storing key ' + varname + ' in file_data')
					file_data[varname] = operation(line, file_data.get(varname))
					#log.debug('stored stuff in key: ' + '|' +varname+'|')
     
			for action in rules_dict['__before__']:
				varname = action[0]
				line_test = action[1]
				search_key = action[2]
				if line_test(line):
					working_key = '__normal__'
     
			for action in rules_dict['__after__']:
				varname = action[0]
				line_test = action[1]
				search_key = action[2]
				if line_test(line):
					#for all the after and before rules, action[2] is the new working key
					#instead of a variable setting function
					working_key = search_key
     
    #at end of lines, check None values to see what to do with them
	for key in rules_dict:
		if key != '__after__' and key != '__before__':
			for action in rules_dict[key]:
				varname = action[0]
				flag = action[3]
				if not file_data.get(varname):
					#print('varname not used in file_data yet')
					if re.search('not_found',flag):
						#print('not_found in flag')
						#print('storing key ' + varname + ' in file_data')
						file_data[varname] = True
					elif re.search('found', flag) or re.search('at_least_2', flag):
						#print('found or at_least_2 in flag')
						#print('storing key ' + varname + ' in file_data')
						file_data[varname] = False
					#right here is where list syntax goes bad.
					#fixed by adding check re.search
					elif not re.search('list', flag):
						#print('list not in flag')
						#print('storing key ' + varname + ' in file_data')
						file_data[varname] = None
        
	return file_data
