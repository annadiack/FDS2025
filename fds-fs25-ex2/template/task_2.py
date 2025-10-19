class CLS:
    """
    Causal Length Set (CLS) - A Conflict-Free Replicated Data Type
    
    This implementation uses causal length to achieve eventual consistency.
    Each element is tracked with a vector of (add_count, remove_count) pairs.
    """
    
    def __init__(self):
        self.elements = {}
        
    def add(self, element):
        if element not in self.elements:
            self.elements[element] = {'add': 0, 'remove': 0}
        
        self.elements[element]['add'] += 1
    
    def remove(self, element):
        if element not in self.elements:
            self.elements[element] = {'add': 0, 'remove': 0}
        
        self.elements[element]['remove'] += 1
    
    def contains(self, element):
        """
        Check if element is in the set.
        An element is considered present if add_count > remove_count
        """
        if element not in self.elements:
            return False
        
        counts = self.elements[element]
        return counts['add'] > counts['remove']
    
    def mutual_sync(self, other_lists):
        """
        Synchronize this list with other CLS instances.
        Takes the maximum of add and remove counts for each element.
        This ensures eventual consistency across all replicas.
        """
        for other_list in other_lists:
            all_elements = set(self.elements.keys()) | set(other_list.elements.keys())
            
            for element in all_elements:
                my_add = self.elements.get(element, {}).get('add', 0)
                my_remove = self.elements.get(element, {}).get('remove', 0)
                
                other_add = other_list.elements.get(element, {}).get('add', 0)
                other_remove = other_list.elements.get(element, {}).get('remove', 0)
                
                merged_add = max(my_add, other_add)
                merged_remove = max(my_remove, other_remove)
                
                if element not in self.elements:
                    self.elements[element] = {}
                self.elements[element]['add'] = merged_add
                self.elements[element]['remove'] = merged_remove
                
                if element not in other_list.elements:
                    other_list.elements[element] = {}
                other_list.elements[element]['add'] = merged_add
                other_list.elements[element]['remove'] = merged_remove
    
    def get_items(self):
        """Get all items currently in the set"""
        return [elem for elem in self.elements if self.contains(elem)]
    
    def __str__(self):
        """String representation of the set"""
        items = self.get_items()
        return f"CLS({items})"
    
    def __repr__(self):
        return self.__str__()


if __name__ == '__main__':
    alice_list = CLS()
    bob_list = CLS()
    
    alice_list.add('Milk')
    alice_list.add('Potato')
    alice_list.add('Eggs')
    
    bob_list.add('Sausage')
    bob_list.add('Mustard')
    bob_list.add('Coke')
    bob_list.add('Potato')
    
    print("Before first sync:")
    print(f"Alice's list: {sorted(alice_list.get_items())}")
    print(f"Bob's list: {sorted(bob_list.get_items())}")
    print(f"Alice Potato: add={alice_list.elements.get('Potato', {}).get('add', 0)}, remove={alice_list.elements.get('Potato', {}).get('remove', 0)}")
    print(f"Bob Potato: add={bob_list.elements.get('Potato', {}).get('add', 0)}, remove={bob_list.elements.get('Potato', {}).get('remove', 0)}")
    
    bob_list.mutual_sync([alice_list])
    
    print("\nAfter first sync:")
    print(f"Alice's list: {sorted(alice_list.get_items())}")
    print(f"Bob's list: {sorted(bob_list.get_items())}")
    print(f"Alice Potato: add={alice_list.elements.get('Potato', {}).get('add', 0)}, remove={alice_list.elements.get('Potato', {}).get('remove', 0)}")
    print(f"Bob Potato: add={bob_list.elements.get('Potato', {}).get('add', 0)}, remove={bob_list.elements.get('Potato', {}).get('remove', 0)}")
    
    alice_list.remove('Sausage')
    alice_list.add('Tofu')
    alice_list.remove('Potato')
    
    print("\nBefore second sync:")
    print(f"Alice's list: {sorted(alice_list.get_items())}")
    print(f"Bob's list: {sorted(bob_list.get_items())}")
    print(f"Alice Potato: add={alice_list.elements.get('Potato', {}).get('add', 0)}, remove={alice_list.elements.get('Potato', {}).get('remove', 0)}")
    print(f"Bob Potato: add={bob_list.elements.get('Potato', {}).get('add', 0)}, remove={bob_list.elements.get('Potato', {}).get('remove', 0)}")
    
    alice_list.mutual_sync([bob_list])
    
    print("\nAfter second sync:")
    print(f"Alice's list: {sorted(alice_list.get_items())}")
    print(f"Bob's list: {sorted(bob_list.get_items())}")
    print(f"Alice Potato: add={alice_list.elements.get('Potato', {}).get('add', 0)}, remove={alice_list.elements.get('Potato', {}).get('remove', 0)}")
    print(f"Bob Potato: add={bob_list.elements.get('Potato', {}).get('add', 0)}, remove={bob_list.elements.get('Potato', {}).get('remove', 0)}")
    
    print("\nBob's list contains 'Potato'?", bob_list.contains('Potato'))