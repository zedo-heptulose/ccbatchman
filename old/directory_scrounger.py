import os
def make_string_test(substring_list, not_substring_list = None):
    #print(substring_list)
    #print(not_substring_list)
    def contains_substrings(line):
    #print ('in contains substring, testing ' + line)
        found = True
        for sub in substring_list:
            #print('testing if ' + sub + ' is in line')
            if sub not in line:
                #print ('not found')
                found = False
        
        if not_substring_list is not None:
            for sub in not_substring_list:
                if sub in line:
                    found = False
        return found
        
    return contains_substrings
    

def find_filenames_recursive(directory, comparison_function = None):
    filename_list = []
    #print('recursive')
    for root, dirs, files in os.walk(directory):
        #print('directory walk')
        for file in files:
           # print('checking filename' + str(file))
            file_path = os.path.join(root, file)
            # Check if the file is a regular file (not a directory) and if the file is the type searched for
            if os.path.isfile(file_path):
                
                if comparison_function is not None:
                    if comparison_function(file):
                        #print('comparison function is used')
                        filename_list.append(file_path)
                else:
                    #print('no comparison function')
                    filename_list.append(file_path)
    return filename_list
                    
def find_filenames_non_recursive(directory, comparison_function = None):
    filename_list = []
    #print('not recursive')
    files_and_dirs = os.listdir(directory)
    # Iterate over each file/directory
    for item in files_and_dirs:
        #print('checking item ' + str(item))
        # Construct the full path
        item_path = os.path.join(directory, item)
        # Check if the item is a regular file
        if os.path.isfile(item_path):
            #print('item is file')
            if comparison_function is not None:
                #print('comparison function is used')
                if comparison_function(item):
                    filename_list.append(item_path)
            else:
                #print('no comparison function, appending ' + str(item_path))
                filename_list.append(item_path)

    return filename_list


def find_filenames_substring_list(directory, substring_list=None, not_substring_list=None, recursive = True):
    comparison_function = None
    if substring_list is not None:
        comparison_function = make_string_test(substring_list, not_substring_list)
    if recursive:
        return find_filenames_recursive(directory,comparison_function)
    else:
        return find_filenames_non_recursive(directory, comparison_function)