from .models import SubroutineCalltree


def remove_null(model: SubroutineCalltree):
    """Function to remove 'Null' entries"""

    queryset = model.objects.filter(child_subroutine=0)
    print("queryset:", queryset)
    for item in queryset:
        print(item.parent_id, item.parent_subroutine, item.child_subroutine)
